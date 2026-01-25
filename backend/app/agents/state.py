"""
state.py - LangGraph State Definition

Defines the structure of data passed between agents in the graph.
"""

from typing import List, Dict, TypedDict, Optional, Annotated
import operator

class Flashcard(TypedDict):
    front: str
    back: str
    confidence: float
    source: str

class AgentState(TypedDict):
    # Input
    pdf_text: str
    chunk_index: int
    total_chunks: int
    
    # Processing
    concepts: List[str]
    generated_cards: Annotated[List[Flashcard], operator.add]
    
    # Output
    final_cards: List[Flashcard]
    errors: List[str]
