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
    pdf_text: str  # Full text (optional if using chunks directly, but good to keep)
    target_count: int # User desired count
    
    # Context
    summary: str # Global summary of the text

    # Map-Reduce
    chunks: List[str] # List of text chunks to process
    
    # Intermediate (Mapped)
    # in Send/Map architecture, each branch might have its own state, 
    # but usually we aggregate results back.
    # We'll use Annotated to merge lists from parallel branches.
    mapped_generated_cards: Annotated[List[Flashcard], operator.add]
    
    # Output
    final_cards: List[Flashcard]
    errors: Annotated[List[str], operator.add]
