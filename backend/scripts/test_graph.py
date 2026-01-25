
import asyncio
import os
import sys
from dotenv import load_dotenv

# Load env vars from backend/.env
load_dotenv(os.path.join(os.getcwd(), 'backend', '.env'))

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.agents.graph import create_flashcard_graph

from app.config import get_settings

async def main():
    print("🚀 Starting Graph Test...")
    settings = get_settings()
    key = settings.gemini_api_key
    if key:
        print(f"🔑 API Key loaded: {key[:4]}...{key[-4:]}")
    else:
        print("❌ API Key NOT loaded!")
    
    # Mock long text (enough to trigger 2 chunks)
    long_text = "Analysis of Algorithms. " * 300 + " \n\n Complexity Theory. " * 300
    
    initial_state = {
        "pdf_text": long_text,
        "chunks": [],
        "mapped_generated_cards": [],
        "final_cards": [],
        "errors": []
    }
    
    try:
        graph = create_flashcard_graph()
        result = await graph.ainvoke(initial_state)
        
        print("\n✅ Test Complete!")
        print(f"Chunks created: {len(result.get('chunks', []))}")
        print(f"Final cards: {len(result.get('final_cards', []))}")
        
        for i, card in enumerate(result.get('final_cards', [])[:3]):
            print(f"Card {i+1}: {card['front']} - {card['back']} (Conf: {card['confidence']})")
            
    except Exception as e:
        print(f"❌ Test Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
