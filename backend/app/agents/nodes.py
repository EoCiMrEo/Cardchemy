"""
nodes.py - LangGraph Agent Nodes for Flashcard Generation

Defines the core logic for each step in the AI pipeline.
"""

import os
import json
from typing import List, Dict, Any

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from app.config import get_settings
from app.agents.state import AgentState, Flashcard

settings = get_settings()

# Initialize Gemini Model
llm = ChatGoogleGenerativeAI(
    model="gemini-pro",
    google_api_key=settings.gemini_api_key,
    temperature=0.2, # Low temperature for factual accuracy
    convert_system_message_to_human=True
)

# --- Pydantic Models for Parsing ---

class ConceptList(BaseModel):
    concepts: List[str] = Field(description="List of key concepts extracted from text")

class GeneratedCard(BaseModel):
    front: str = Field(description="Question or term")
    back: str = Field(description="Answer or definition")
    source_snippet: str = Field(description="Short text snippet justifying the answer")

class CardList(BaseModel):
    cards: List[GeneratedCard] = Field(description="List of generated flashcards")

class ReviewResult(BaseModel):
    confidence: float = Field(description="Score between 0.0 and 1.0")
    feedback: str = Field(description="Critique of the card quality")


# --- Node Functions ---

async def extract_concepts(state: AgentState) -> Dict:
    """
    Agent 1: Extract key concepts from the text chunk.
    """
    print(f"🔍 Extracting concepts from chunk {state['chunk_index']}...")
    
    parser = PydanticOutputParser(pydantic_object=ConceptList)
    
    prompt = PromptTemplate(
        template="""
        You are an expert educator. Identify the most important concepts, terms, definitions, and facts from the text below that are suitable for flashcards.
        Focus on concrete, testable information. output valid JSON matching the schema.

        TEXT:
        {text}

        {format_instructions}
        """,
        input_variables=["text"],
        partial_variables={"format_instructions": parser.get_format_instructions()}
    )
    
    chain = prompt | llm | parser
    
    try:
        result = await chain.ainvoke({"text": state['pdf_text']})
        return {"concepts": result.concepts}
    except Exception as e:
        print(f"❌ Error extracting concepts: {e}")
        return {"concepts": [], "errors": [str(e)]}


async def generate_cards(state: AgentState) -> Dict:
    """
    Agent 2: Generate Front/Back flashcards for each concept.
    """
    print(f"✍️ Generating cards for {len(state['concepts'])} concepts...")
    
    if not state['concepts']:
        return {"generated_cards": []}

    parser = PydanticOutputParser(pydantic_object=CardList)
    
    prompt = PromptTemplate(
        template="""
        You are a flashcard generator. Create high-quality flashcards for the following concepts based *only* on the provided text context.
        
        Rules:
        1. Front should be a clear question or term.
        2. Back should be a concise but complete answer.
        3. Include a very short source snippet from the text verbatim.
        4. Output valid JSON.

        CONTEXT TEXT:
        {text}

        CONCEPTS TO COVER:
        {concepts}

        {format_instructions}
        """,
        input_variables=["text", "concepts"],
        partial_variables={"format_instructions": parser.get_format_instructions()}
    )

    chain = prompt | llm | parser
    
    try:
        result = await chain.ainvoke({
            "text": state['pdf_text'], 
            "concepts": ", ".join(state['concepts'])
        })
        
        # Convert to internal format
        cards = []
        for card in result.cards:
            cards.append({
                "front": card.front,
                "back": card.back,
                "source": card.source_snippet,
                "confidence": 0.5 # Default, will be updated by reviewer
            })
            
        return {"generated_cards": cards}
        
    except Exception as e:
        print(f"❌ Error generating cards: {e}")
        return {"generated_cards": [], "errors": [str(e)]}


async def review_cards(state: AgentState) -> Dict:
    """
    Agent 3: Review generated cards and assign confidence scores.
    """
    print(f"🧐 Reviewing {len(state['generated_cards'])} cards...")
    
    reviewed_cards = []
    
    # Review batch (simplified for speed, ideally one by one or small batches)
    # For MVP, we'll use a simpler heuristic or a single LLM call for the batch if small.
    # Let's verify the first 5 for now to save tokens, or all if few.
    
    for card in state['generated_cards']:
        # Simple heuristic check first
        if len(card['front']) < 5 or len(card['back']) < 5:
            card['confidence'] = 0.1
            reviewed_cards.append(card)
            continue
            
        # Optional: Deep LLM review could go here. 
        # For now, we'll just bump confidence if it looks well-formed.
        # Real implementation would verify against text source.
        card['confidence'] = 0.8 
        reviewed_cards.append(card)

    return {"final_cards": reviewed_cards}
