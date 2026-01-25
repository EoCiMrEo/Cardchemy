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
    model="gemini-3-flash-preview", # Optimized for structured output if available, else gemini-pro
    google_api_key=settings.gemini_api_key,
    temperature=0.2,
    convert_system_message_to_human=True
)

# --- Pydantic Models for Parsing ---

class GeneratedCard(BaseModel):
    front: str = Field(description="Question or term")
    back: str = Field(description="Answer or definition")
    source_snippet: str = Field(description="Short text snippet justifying the answer")
    confidence: float = Field(description="Self-assessed confidence 0.0-1.0", default=0.8)

class CardList(BaseModel):
    cards: List[GeneratedCard] = Field(description="List of generated flashcards")


# --- Node Functions ---

async def summarize_text(state: AgentState) -> Dict:
    """
    Summarize the full text to provide global context.
    """
    print("🧠 Summarizing text for global context...")
    text = state.get("pdf_text", "")[:30000] # Limit for summarization context
    
    prompt = PromptTemplate(
        template="""
        Summarize the following text into key concepts and high-level topics.
        This summary will be used to guide flashcard generation to ensure comprehensive coverage without repetition.
        Keep it concise (bullet points).
        
        TEXT:
        {text}
        """,
        input_variables=["text"]
    )
    
    chain = prompt | llm
    try:
        response = await chain.ainvoke({"text": text})
        summary = response.content
        print(f"📝 Summary generated: {summary[:100]}...")
        return {"summary": summary}
    except Exception as e:
        print(f"⚠️ Summarization failed: {e}")
        return {"summary": "No summary available."}


def split_text(state: AgentState) -> Dict:
    """
    Splits the full PDF text into manageable chunks.
    """
    print("✂️ Splitting text into chunks...")
    full_text = state.get('pdf_text', '')
    print(f"📄 Full text length: {len(full_text)} chars")
    
    # Simple character splitting for now. content-aware splitting is better but complex.
    chunk_size = 4000 # Safety margin for context window
    overlap = 200
    
    chunks = []
    start = 0
    while start < len(full_text):
        end = start + chunk_size
        chunk = full_text[start:end]
        chunks.append(chunk)
        start += (chunk_size - overlap)
        
    print(f"Created {len(chunks)} chunks.")
    return {"chunks": chunks}


async def generate_cards_from_chunk(state: Dict) -> Dict:
    """
    Map Step: Generate cards for a single chunk.
    State input here is just the chunk wrapper from the Send() content usually, 
    but in LangGraph map-reduce, we might receive specific state.
    
    We will assume specific structure passed by Send() or Map: {'chunk': str, 'summary': str}
    """
    chunk_text = state.get('chunk', '')
    summary = state.get('summary', '')
    
    if not chunk_text:
        return {"mapped_generated_cards": []}
        
    print(f"⚡ Processing chunk ({len(chunk_text)} chars)...")
    
    parser = PydanticOutputParser(pydantic_object=CardList)
    
    prompt = PromptTemplate(
        template="""
        You are a flashcard generator. Create high-quality flashcards based on the provided text chunk.
        
        GLOBAL CONTEXT (The bigger picture):
        {summary}
        
        INSTRUCTIONS:
        1. Focus on specific details found in the CHUNK, but relate them to the global context.
        2. Avoid generic questions if the answer is not in the chunk.
        3. Do NOT just repeat the Global Context; only use it for understanding.
        4. Create 3-5 cards per chunk.
        
        Rules:
        1. Front should be a clear question or term.
        2. Back should be a concise but complete answer.
        3. Include a very short source snippet from the text verbatim.
        4. Assign a confidence score (0.0-1.0) based on how well the text supports the card.
        5. Output valid JSON.

        CHUNK TEXT:
        {text}

        {format_instructions}
        """,
        input_variables=["text", "summary"],
        partial_variables={"format_instructions": parser.get_format_instructions()}
    )

    chain = prompt | llm | parser
    
    try:
        result = await chain.ainvoke({"text": chunk_text, "summary": summary})
        
        print(f"✨ Generated {len(result.cards)} cards for chunk.")
        
        # Convert to internal format
        cards = []
        for card in result.cards:
            cards.append({
                "front": card.front,
                "back": card.back,
                "source": card.source_snippet,
                "confidence": card.confidence
            })
            
        return {"mapped_generated_cards": cards}
        
    except Exception as e:
        print(f"❌ Error generating cards for chunk: {e}")
        import traceback
        traceback.print_exc()
        return {"mapped_generated_cards": [], "errors": [str(e)]}


async def reduce_and_review(state: AgentState) -> Dict:
    """
    Reduce Step: Aggregate all cards, deduplicate, and finalize.
    """
    all_cards = state.get('mapped_generated_cards', [])
    target_count = state.get('target_count', 20)
    print(f"🔄 Reducing {len(all_cards)} cards. Target: {target_count}")
    
    # Simple deduplication by Front text
    unique_cards: Dict[str, Flashcard] = {}
    
    for card in all_cards:
        key = card['front'].strip().lower()
        if key not in unique_cards:
            unique_cards[key] = card
        else:
            # If duplicate, keep higher confidence or longer back
            existing = unique_cards[key]
            if card['confidence'] > existing['confidence']:
                unique_cards[key] = card
                
    # Propagate errors from mapped tasks
    errors = state.get('errors', [])
    for error in errors:
        print(f"⚠️ Found error in sub-task: {error}")
    
    final_list = list(unique_cards.values())
    
    # Sort by confidence + length (proxy for quality)
    final_list.sort(key=lambda x: (x['confidence'], len(x['back'])), reverse=True)
    
    # Limit to target count
    final_list = final_list[:target_count]
    
    print(f"✅ Finalizing {len(final_list)} unique cards (Target: {target_count}).")
    
    # If no cards and we have errors, ensure we signal failure
    if not final_list and errors:
        return {"final_cards": [], "errors": errors}
    
    return {"final_cards": final_list}
