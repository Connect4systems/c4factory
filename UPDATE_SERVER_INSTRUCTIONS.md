# Update Server with Latest Fixes

## Problem
The server is still using the old code from the main branch. You need to pull the latest changes from the `blackboxai/fix-hooks-syntax-error` branch that contains all the fixes.

## Solution - Update the App on Server

### Option 1: Pull the Fix Branch (Recommended for Testing)

```bash
# Navigate to the c4factory app directory
cd ~/frappe-bench/apps/c4factory

# Check current branch
git branch

# Fetch all branches from remote
git fetch origin

# Switch to the fix branch
git checkout blackboxai/fix-hooks-syntax-error

# Pull latest changes
git pull origin blackboxai/fix-hooks-syntax-error

# Go back to bench directory
cd ~/frappe-bench

# Restart bench
bench restart

# Try installing again
bench --site develop.connect4systems.com install-app c4factory
```

### Option 2: Wait for PR Merge (Recommended for Production)

1. Create the pull request using the link in CREATE_PULL_REQUEST.md
2. Wait for the PR to be reviewed and merged into main
3. Then on the server:

```bash
cd ~/frappe-bench/apps/c4factory
git checkout main
git pull origin main
cd ~/frappe-bench
bench restart
bench --site develop.connect4systems.com install-app c4factory
```

### Option 3: Remove and Re-add App with Branch

```bash
# Remove the app (if not installed on any site yet)
cd ~/frappe-bench
bench remove-app c4factory

# Get the app from the specific branch
bench get-app https://github.com/c4erp/c4factory --branch blackboxai/fix-hooks-syntax-error

# Install on site
bench --site develop.connect4systems.com install-app c4factory
```

## Verification

After pulling the latest changes, verify the files have the `dt` field:

```bash
cd ~/frappe-bench/apps/c4factory

# Check stock_entry.json
grep -A 2 '"dt"' c4factory/c4factory/custom/stock_entry.json

# Should show:
#   "dt": "Stock Entry",
#   "fieldname": "c4_pick_list",

# Check pick_list.json
grep -A 2 '"dt"' c4factory/c4factory/custom/pick_list.json

# Should show multiple entries with "dt": "Pick List"

# Check pick_list_item.json  
grep -A 2 '"dt"' c4factory/c4factory/custom/pick_list_item.json

# Should show multiple entries with "dt": "Pick List Item"
```

## Why This Happened

When you ran `bench get-app https://github.com/c4erp/c4factory`, it cloned the **main** branch by default, which doesn't have our fixes yet. Our fixes are in the `blackboxai/fix-hooks-syntax-error` branch and need to be either:
1. Pulled directly from that branch for testing, OR
2. Merged into main via pull request for production use

## Recommended Workflow

For immediate testing:
```bash
cd ~/frappe-bench/apps/c4factory
git fetch origin
git checkout blackboxai/fix-hooks-syntax-error
git pull origin blackboxai/fix-hooks-syntax-error
cd ~/frappe-bench
bench restart
bench --site develop.connect4systems.com install-app c4factory
```

This should resolve the installation error and allow the app to install successfully.
