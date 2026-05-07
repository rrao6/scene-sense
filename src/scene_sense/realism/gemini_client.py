"""Thin wrapper around google-genai with on-disk caching and grounding support."""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types as genai_types
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .config import RealismConfig

log = logging.getLogger(__name__)


class GeminiClient:
    def __init__(self, cfg: RealismConfig):
        self.cfg = cfg
        self._client = genai.Client(api_key=cfg.gemini_api_key)

    def _cache_path(self, namespace: str, payload: dict[str, Any]) -> Path:
        blob = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        digest = hashlib.sha256(blob).hexdigest()[:32]
        return self.cfg.cache_dir / namespace / f"{digest}.json"

    def _read_cache(self, path: Path) -> dict[str, Any] | None:
        if not (self.cfg.enable_cache and path.exists()):
            return None
        try:
            return json.loads(path.read_text())
        except Exception:
            return None

    def _write_cache(self, path: Path, payload: dict[str, Any]) -> None:
        if not self.cfg.enable_cache:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, default=str))

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=2, max=20),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def _raw_generate(
        self,
        *,
        model: str,
        contents: str,
        response_schema: dict[str, Any] | None = None,
        tools: list[Any] | None = None,
        system_instruction: str | None = None,
        temperature: float = 0.2,
    ) -> genai_types.GenerateContentResponse:
        cfg_kwargs: dict[str, Any] = {"temperature": temperature}
        if system_instruction:
            cfg_kwargs["system_instruction"] = system_instruction
        if response_schema is not None:
            cfg_kwargs["response_mime_type"] = "application/json"
            cfg_kwargs["response_schema"] = response_schema
        if tools:
            cfg_kwargs["tools"] = tools
        config = genai_types.GenerateContentConfig(**cfg_kwargs)
        return self._client.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )

    def structured(
        self,
        *,
        namespace: str,
        prompt: str,
        response_schema: dict[str, Any],
        system_instruction: str | None = None,
        model: str | None = None,
        temperature: float = 0.1,
    ) -> dict[str, Any]:
        """Structured-output call. JSON-schema constrained. Cached by payload hash."""
        model = model or self.cfg.gemini_model_fast
        cache_key = {
            "namespace": namespace,
            "model": model,
            "prompt": prompt,
            "schema": response_schema,
            "sys": system_instruction,
            "temp": temperature,
        }
        cpath = self._cache_path(namespace, cache_key)
        cached = self._read_cache(cpath)
        if cached is not None:
            return cached["data"]
        resp = self._raw_generate(
            model=model,
            contents=prompt,
            response_schema=response_schema,
            system_instruction=system_instruction,
            temperature=temperature,
        )
        text = resp.text or "{}"
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            log.warning("structured() got non-JSON response; raw=%s", text[:200])
            data = {}
        self._write_cache(cpath, {"data": data, "raw": text})
        return data

    def grounded(
        self,
        *,
        namespace: str,
        prompt: str,
        system_instruction: str | None = None,
        model: str | None = None,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        """Google Search-grounded call. Returns {text, citations[], raw_queries[]}."""
        model = model or self.cfg.gemini_model_deep
        cache_key = {
            "namespace": namespace,
            "model": model,
            "prompt": prompt,
            "sys": system_instruction,
            "temp": temperature,
            "grounded": True,
        }
        cpath = self._cache_path(namespace, cache_key)
        cached = self._read_cache(cpath)
        if cached is not None:
            return cached["data"]

        tool = genai_types.Tool(google_search=genai_types.GoogleSearch())
        resp = self._raw_generate(
            model=model,
            contents=prompt,
            system_instruction=system_instruction,
            temperature=temperature,
            tools=[tool],
        )
        text = resp.text or ""
        citations: list[dict[str, Any]] = []
        queries: list[str] = []
        try:
            for cand in (resp.candidates or []):
                gm = getattr(cand, "grounding_metadata", None)
                if not gm:
                    continue
                for q in (getattr(gm, "web_search_queries", None) or []):
                    queries.append(str(q))
                for chunk in (getattr(gm, "grounding_chunks", None) or []):
                    web = getattr(chunk, "web", None)
                    if not web:
                        continue
                    citations.append(
                        {
                            "url": getattr(web, "uri", None),
                            "title": getattr(web, "title", None),
                        }
                    )
        except Exception as exc:  # noqa: BLE001
            log.warning("grounded(): metadata parse failed: %s", exc)
        data = {"text": text, "citations": citations, "queries": queries}
        self._write_cache(cpath, {"data": data})
        return data
