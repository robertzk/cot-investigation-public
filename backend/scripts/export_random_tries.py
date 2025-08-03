import asyncio
from sqlalchemy import select, func
import json
from app.models import async_session, Problem, CotTrie

async def export_random_tries():
    async with async_session() as session:
        query = (
            select(CotTrie, Problem.question)
            .join(Problem, CotTrie.problem_id == Problem.id)
            .where(CotTrie.model == "google/gemma-2-2b-it")
            .order_by(func.random())
            .limit(3)
        )
        
        result = await session.execute(query)
        tries_data = []
        
        for trie_record, question in result:
            tries_data.append({
                "trie": trie_record.trie,  # This is already JSON-serializable
                "question": question,
                "model": trie_record.model,
                "dataset": trie_record.dataset,
                "problem_id": trie_record.problem_id
            })
        
        # Save to file
        with open('gemma_tries.json', 'w') as f:
            json.dump(tries_data, f, indent=2)
        
        print(f"Saved {len(tries_data)} tries to gemma_tries.json")

if __name__ == "__main__":
    asyncio.run(export_random_tries())
