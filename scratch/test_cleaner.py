from app.core.repost.logic import MessageCleaner

def test_nuke_and_replace():
    # This is what your messy metadata looks like
    original_text = "👤 Creator: sillylostpoet\n📁 File: sillylostpoet_433.mp4\n🔗 t.me/storage_channel"
    
    # This is your new sales pitch
    my_sales_pitch = "🔞 FULL VIDEO IN VIP! Join now: t.me/my_vip_link"
    
    print("--- 🧪 TESTING NUKE & REPLACE (MODE 3) ---")
    print(f"ORIGINAL:\n{original_text}\n")
    
    # Run the cleaner in Mode 3
    result = MessageCleaner.clean(original_text, mode=3, replacement=my_sales_pitch)
    
    print(f"CLEANED (FINAL POST):\n{result}\n")
    
    if result == my_sales_pitch:
        print("✅ SUCCESS: The messy metadata was completely replaced!")
    else:
        print("❌ FAILED: The output didn't match the replacement.")

if __name__ == "__main__":
    test_nuke_and_replace()
