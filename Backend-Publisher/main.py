import os
import json
from supabase import create_client, Client

# ==========================================
# Little Mere News - Publisher Script
# ==========================================

def main():
    print("[1/3] Initializing Publisher...")
    
    # Load environment variables (provided securely by the Master Script)
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY") # This should be the service_role key
    
    if not supabase_url or not supabase_key:
        print("[FATAL] SUPABASE_URL and SUPABASE_KEY must be set in the environment.")
        return

    supabase: Client = create_client(supabase_url, supabase_key)
    input_file = "/home/lmnadmin/news_to_publish.json"

    if not os.path.exists(input_file):
        print(f"[WARNING] File {input_file} not found. Nothing to publish today.")
        return

    print("[2/3] Reading processed news payload...")
    with open(input_file, 'r', encoding='utf-8') as f:
        news_items = json.load(f)

    if not news_items:
        print("[INFO] No news items to publish.")
        return

    print(f"[3/3] Uploading {len(news_items)} items to Supabase...")
    
    success_count = 0
    for item in news_items:
        try:
            # Insert the record.
            # If the source_url already exists, the unique constraint in Supabase will throw an error,
            # which is completely expected and handles duplicate-prevention elegantly.
            response = supabase.table("news").insert(item).execute()
            print(f"  [+] Published: {item.get('title_en')}")
            success_count += 1
            
        except Exception as e:
            error_msg = str(e).lower()
            if "duplicate key value" in error_msg or "unique constraint" in error_msg:
                print(f"  [SKIP] Already in database: {item.get('title_en')}")
            else:
                print(f"  [ERROR] Failed to publish {item.get('title_en')}: {e}")

    print("=========================================")
    print(f" Upload Complete: {success_count}/{len(news_items)} new articles added.")
    print("=========================================")
    
    # Delete the payload file to prevent re-processing tomorrow if harvester fails
    os.remove(input_file)

if __name__ == "__main__":
    main()
