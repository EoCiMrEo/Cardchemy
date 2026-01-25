"""
graph.py - LangGraph Workflow Definition

Wires together the agents into an executable graph.
"""

from langgraph.graph import StateGraph, END
from langgraph.constants import Send
from app.agents.state import AgentState
from app.agents.nodes import split_text, generate_cards_from_chunk, reduce_and_review, summarize_text

def map_chunks(state: AgentState):
    """
    Map function to create Send objects for parallel processing.
    """
    chunks = state.get('chunks', [])
    summary = state.get('summary', '')
    return [
        Send("generator", {"chunk": chunk, "summary": summary}) for chunk in chunks
    ]

def create_flashcard_graph():
    """
    Constructs the flashcard generation workflow graph.
    """
    workflow = StateGraph(AgentState)

    # Add Nodes
    workflow.add_node("summarizer", summarize_text)
    workflow.add_node("splitter", split_text)
    workflow.add_node("generator", generate_cards_from_chunk)
    workflow.add_node("reducer", reduce_and_review)

    # Define Edges
    workflow.set_entry_point("summarizer")
    
    # Summarizer -> Splitter
    workflow.add_edge("summarizer", "splitter")
    
    # Splitter -> Map (conditional edge to generator)
    workflow.add_conditional_edges(
        "splitter",
        map_chunks,
        ["generator"]
    )
    
    # Generator -> Reducer
    # Since Generator is parallel, all branches must complete before Reducer runs.
    # LangGraph handles this collection automatically if wired correctly.
    workflow.add_edge("generator", "reducer")
    
    # Reducer -> End
    workflow.add_edge("reducer", END)

    # Compile
    return workflow.compile()
