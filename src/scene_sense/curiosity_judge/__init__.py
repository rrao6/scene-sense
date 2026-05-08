"""LLM Curiosity Judge — viewer-voice scoring of pause-screen cards.

This is the model Lia is. Given a finalized card, a fresh-context Gemini call
rates it 1-5 on 4 dimensions and returns a verdict. Feeds the finalizer as a
new scoring dimension with high weight.
"""
