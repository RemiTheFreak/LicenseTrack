import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

if not url or not key:
    raise ValueError(
        "Missing Supabase credentials. Check your .env file."
    )

supabase = create_client(url, key)

try:
    result = (
        supabase.table("companies")
        .select("id")
        .limit(1)
        .execute()
    )
    print("Connection successful!")
    print("Companies table is accessible.")
except Exception as error:
    print("Connection or permission error:", error)