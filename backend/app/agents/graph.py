"""
graph.py - LangGraph Workflow Definition

Wires together the agents into an executable graph.
"""

from langgraph.graph import StateGraph, END
from app.agents.state import AgentState
from app.agents.nodes import extract_concepts, generate_cards, review_cards

def create_flashcard_graph():
    """
    Constructs the flashcard generation workflow graph.
    """
    workflow = StateGraph(AgentState)

    # Add Nodes
    workflow.add_node("extractor", extract_concepts)
    workflow.add_node("generator", generate_cards)
    workflow.add_node("reviewer", review_cards)

    # Define Edges
    workflow.set_entry_point("extractor")
    
    # Extractor -> Generator
    workflow.add_edge("extractor", "generator")
    
    # Generator -> Reviewer
    workflow.add_edge("generator", "reviewer")
    
    # Reviewer -> End
    workflow.add_edge("reviewer", END)

    # Compile
    return workflow.compile()
