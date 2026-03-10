#!/usr/bin/env python3
"""Quick check of database result counts."""
from api.services.supabase import get_supabase_client

supabase = get_supabase_client()

# Count 4D results
resp_4d = supabase.table('lottery_results').select('id').eq('game_type', '4D').execute()
count_4d = len(resp_4d.data)

# Count TOTO results
resp_toto = supabase.table('lottery_results').select('id').eq('game_type', 'TOTO').execute()
count_toto = len(resp_toto.data)

print(f"📊 Database Summary")
print(f"{'='*40}")
print(f"4D results:   {count_4d}")
print(f"TOTO results: {count_toto}")
print(f"{'='*40}")
print(f"Total:        {count_4d + count_toto}")
print(f"{'='*40}")
