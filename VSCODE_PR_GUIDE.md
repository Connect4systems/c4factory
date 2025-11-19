# Create Pull Request Using VS Code - Step by Step Guide

Since Git is not available in your PowerShell PATH, follow these steps to create a Pull Request using VS Code's built-in Source Control feature.

## Method 1: Using VS Code Source Control (Recommended)

### Step 1: Open Source Control
1. Press `Ctrl + Shift + G` or click the Source Control icon in the left sidebar
2. You should see all your changed files listed

### Step 2: Review Changes
You should see these files:
- ✅ **New Files (14)**:
  - c4factory/c4factory/custom/pick_list.json
  - c4factory/c4factory/custom/pick_list_item.json
  - c4factory/c4factory/custom/stock_entry.json
  - c4factory/c4_manufacturing/pick_list_hooks.py
  - c4factory/api/work_order_pick_list.py
  - c4factory/api/pick_list_stock.py
  - c4factory/public/js/doctype/work_order.js
  - c4factory/patches/v1_0/setup_pick_list_custom_fields.py
  - TODO.md
  - IMPLEMENTATION_SUMMARY.md
  - GIT_PUSH_INSTRUCTIONS.md
  - create_pull_request.ps1
  - VSCODE_PR_GUIDE.md
  
- ✅ **Modified Files (5)**:
  - c4factory/c4_manufacturing/work_order_hooks.py
  - c4factory/c4_manufacturing/stock_entry_hooks.py
  - c4factory/patches/v1_0/setup_work_order_custom_fields.py
  - c4factory/hooks.py
  - c4factory/public/js/doctype/pick_list.js

### Step 3: Stage All Changes
1. Click the `+` (plus) icon next to "Changes" to stage all files
2. OR hover over each file and click the `+` icon individually

### Step 4: Create a New Branch
1. Click on the branch name in the bottom-left corner of VS Code (usually shows "main" or "develop")
2. Select "Create new branch..."
3. Enter branch name: `blackboxai/pick-list-manufacturing`
4. Press Enter

### Step 5: Commit Changes
1. In the Source Control panel, you'll see a text box at the top
2. Enter this commit message:

```
feat: Implement Pick List-based manufacturing system

Features:
- Editable Work Order items before submission (c4_required_items)
- Pick List creation from Work Order with balance calculation
- Stock Entry creation from Pick List (not BOM)
- Partial Stock Entry support
- Automatic Pick List status management (Open/Completed)
- Consumed quantity tracking and balance updates
- Complete hook integration for Work Order, Pick List, and Stock Entry
- Scrap items support in new flow

Technical Changes:
- Added 14 new files (hooks, APIs, UI scripts, custom fields, docs)
- Modified 5 existing files (hooks, patches)
- Created comprehensive documentation

Files Created:
- Custom field definitions for Pick List, Pick List Item, Stock Entry
- pick_list_hooks.py for validation and status management
- work_order_pick_list.py API for Pick List creation
- pick_list_stock.py API for Stock Entry creation
- work_order.js and pick_list.js for UI enhancements
- Database patches for custom fields
- Documentation files

Files Modified:
- work_order_hooks.py - Added required items copying and balance calculation
- stock_entry_hooks.py - Added Pick List tracking on submit/cancel
- setup_work_order_custom_fields.py - Added c4_required_items fields
- hooks.py - Registered all new hooks and patches
- pick_list.js - Added Stock Entry creation functionality

Breaking Changes: None
Backward Compatibility: Yes - Old BOM-based flow still works
```

3. Click the checkmark (✓) icon or press `Ctrl + Enter` to commit

### Step 6: Push to Remote
1. Click the "..." menu in the Source Control panel
2. Select "Push" or "Publish Branch"
3. If prompted, select "origin" as the remote
4. VS Code will push your branch to GitHub

### Step 7: Create Pull Request
After pushing, VS Code will show a notification:
1. Click "Create Pull Request" in the notification
2. OR click the notification icon in the bottom-left status bar
3. OR go to GitHub in your browser

If using browser:
1. Go to your repository on GitHub
2. You'll see a banner: "blackboxai/pick-list-manufacturing had recent pushes"
3. Click "Compare & pull request"

### Step 8: Fill Pull Request Details

**Title:**
```
feat: Implement Pick List-based manufacturing system
```

**Description:**
```markdown
## Overview
This PR implements a complete Pick List-based manufacturing system for C4Factory ERPNext app.

## Features Implemented
- ✅ Editable Work Order items before submission
- ✅ Pick List creation from Work Order with balance tracking
- ✅ Stock Entry creation from Pick List (not BOM)
- ✅ Partial Stock Entry support
- ✅ Automatic Pick List status management (Open/Completed)
- ✅ Consumed quantity tracking and balance updates

## Technical Changes
- **New Files**: 14 files (hooks, APIs, UI scripts, custom fields, documentation)
- **Modified Files**: 5 files (hooks, patches)
- **Backward Compatible**: Yes - Old BOM-based flow still works

## Files Created
1. Custom field definitions (pick_list.json, pick_list_item.json, stock_entry.json)
2. Server hooks (pick_list_hooks.py)
3. API endpoints (work_order_pick_list.py, pick_list_stock.py)
4. UI enhancements (work_order.js, pick_list.js)
5. Database patches (setup_pick_list_custom_fields.py)
6. Documentation (TODO.md, IMPLEMENTATION_SUMMARY.md, GIT_PUSH_INSTRUCTIONS.md)

## Files Modified
1. work_order_hooks.py - Required items copying and balance calculation
2. stock_entry_hooks.py - Pick List tracking
3. setup_work_order_custom_fields.py - c4_required_items fields
4. hooks.py - Hook registrations
5. pick_list.js - Stock Entry creation

## Testing Required
- [ ] Run `bench migrate` to apply patches
- [ ] Test complete workflow: Work Order → Pick List → Stock Entry
- [ ] Verify status updates and balance calculations
- [ ] Test partial Stock Entry functionality
- [ ] Test Stock Entry cancellation and balance recalculation

## Documentation
- See IMPLEMENTATION_SUMMARY.md for complete technical documentation
- See TODO.md for implementation progress
- See GIT_PUSH_INSTRUCTIONS.md for Git workflow guide

## Breaking Changes
None

## Backward Compatibility
Yes - The old BOM-based manufacturing flow continues to work alongside the new Pick List-based flow.
```

### Step 9: Submit Pull Request
1. Select the base branch (usually "main" or "develop")
2. Click "Create pull request"
3. Done! 🎉

---

## Method 2: Using GitHub Desktop (Alternative)

If VS Code's Git integration doesn't work:

1. **Download GitHub Desktop**: https://desktop.github.com/
2. **Install and sign in** to your GitHub account
3. **Add repository**: File → Add Local Repository → Select `d:\C4erp-APP\c4factory`
4. **Create branch**: Current Branch → New Branch → Name: `blackboxai/pick-list-manufacturing`
5. **Review changes**: All files will be shown in the left panel
6. **Commit**: 
   - Enter commit message (use the message from Step 5 above)
   - Click "Commit to blackboxai/pick-list-manufacturing"
7. **Push**: Click "Publish branch" or "Push origin"
8. **Create PR**: Click "Create Pull Request" button in GitHub Desktop

---

## Method 3: Install Git (If you want to use command line)

1. **Download Git**: https://git-scm.com/download/win
2. **Install** with default options
3. **Restart** your terminal/PowerShell
4. **Run the script**: `powershell -ExecutionPolicy Bypass -File create_pull_request.ps1`

---

## Troubleshooting

### "Git not found" in VS Code
1. Install Git from https://git-scm.com/download/win
2. Restart VS Code
3. Go to File → Preferences → Settings
4. Search for "git.path"
5. Set it to: `C:\Program Files\Git\bin\git.exe`

### "Authentication failed"
1. VS Code will prompt for GitHub credentials
2. Use your GitHub username and Personal Access Token (not password)
3. Create token at: https://github.com/settings/tokens
4. Required scopes: `repo`, `workflow`

### "No changes detected"
1. Make sure you're in the correct directory
2. Check if files are saved (File → Save All)
3. Refresh Source Control panel

### "Cannot push to remote"
1. Check your internet connection
2. Verify you have push access to the repository
3. Try authenticating again

---

## Quick Reference

**VS Code Shortcuts:**
- `Ctrl + Shift + G` - Open Source Control
- `Ctrl + Enter` - Commit staged changes
- `Ctrl + Shift + P` - Command Palette (type "Git: Push")

**Branch Naming:**
- Feature: `blackboxai/pick-list-manufacturing`
- Alternative: `feature/pick-list-manufacturing`

**Commit Message Format:**
```
feat: Brief description

Detailed description
- Bullet points
- More details
```

---

## After Creating PR

1. ✅ Wait for code review
2. ✅ Address any feedback
3. ✅ Once approved, merge the PR
4. ✅ Run `bench migrate` on your server
5. ✅ Test the new functionality

---

## Need Help?

If you encounter any issues:
1. Check the error message carefully
2. Ensure Git is installed (for VS Code integration)
3. Verify you have repository access
4. Try GitHub Desktop as an alternative
5. Check your GitHub authentication

For more details, see:
- IMPLEMENTATION_SUMMARY.md - Technical documentation
- GIT_PUSH_INSTRUCTIONS.md - Alternative Git methods
- create_pull_request.ps1 - Automated script (requires Git)
