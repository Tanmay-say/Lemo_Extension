# Fix: User Account Inactive (403 Error)

## Problem
User exists in database but `is_active` is set to `False`, causing 403 Forbidden errors when trying to authenticate.

## Solution: Activate User Account

### Option 1: Using Prisma Studio (GUI)

```bash
# From lemo-fastapi directory
prisma studio
```

1. Navigate to the `users` table
2. Find the user by wallet address
3. Set `is_active` to `true`
4. Save

### Option 2: Using SQL Direct Query

```bash
# Connect to your PostgreSQL database
psql -U your_username -d your_database_name
```

```sql
-- Activate specific user by wallet address
UPDATE users 
SET is_active = true 
WHERE wallet_address = '0x286bd33A27079f28a4B4351a85Ad7f23A04BDdfC';

-- Verify
SELECT id, email, wallet_address, is_active FROM users 
WHERE wallet_address = '0x286bd33A27079f28a4B4351a85Ad7f23A04BDdfC';
```

### Option 3: Create a Python Script

Create `activate_user.py` in lemo-fastapi directory:

```python
import asyncio
from prisma import Prisma

async def activate_user(wallet_address: str):
    prisma = Prisma()
    await prisma.connect()
    
    try:
        user = await prisma.users.update(
            where={'wallet_address': wallet_address},
            data={'is_active': True}
        )
        print(f"✅ User activated: {user.email} ({user.wallet_address})")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await prisma.disconnect()

# Replace with your wallet address
WALLET_ADDRESS = "0x286bd33A27079f28a4B4351a85Ad7f23A04BDdfC"
asyncio.run(activate_user(WALLET_ADDRESS))
```

Run it:
```bash
python activate_user.py
```

### Option 4: Activate All Users

If you want to activate all inactive users:

```sql
UPDATE users SET is_active = true WHERE is_active = false;
```

## Prevention: Auto-Activate New Users

To prevent this in the future, ensure `is_active` is set to `True` by default when creating users.

In `controllers/authentication.py` (already done at line 176):

```python
create_data = {
    "id": normalizedWalletAddress,
    "wallet_address": normalizedWalletAddress,
    "email": normalizedEmail,
    "first_name": firstName.strip(),
    "last_name": lastName.strip(),
    "is_active": True,  # ✅ This is already correct
}
```

## Verify Fix

After activating the user:

1. Reload the extension
2. Connect wallet
3. Should see: "User authenticated: [user data]" in console
4. User profile should display in Wallet tab
5. Chat should work normally

## Still Having Issues?

Check:
1. Backend is running: `python run.py`
2. Backend URL in extension Settings matches (default: http://localhost:8000)
3. Database connection is working
4. Check backend logs for detailed error messages

