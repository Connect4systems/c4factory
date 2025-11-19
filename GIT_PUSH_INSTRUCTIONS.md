# Instructions to Push Changes to Repository

## Files Changed Summary

### New Files Created (13 files):
```
c4factory/c4factory/custom/pick_list.json
c4factory/c4factory/custom/pick_list_item.json
c4factory/c4factory/custom/stock_entry.json
c4factory/c4_manufacturing/pick_list_hooks.py
c4factory/api/work_order_pick_list.py
c4factory/api/pick_list_stock.py
c4factory/public/js/doctype/work_order.js
c4factory/patches/v1_0/setup_pick_list_custom_fields.py
TODO.md
IMPLEMENTATION_SUMMARY.md
GIT_PUSH_INSTRUCTIONS.md
```

### Modified Files (5 files):
```
c4factory/c4_manufacturing/work_order_hooks.py
c4factory/c4_manufacturing/stock_entry_hooks.py
c4factory/patches/v1_0/setup_work_order_custom_fields.py
c4factory/hooks.py
c4factory/public/js/doctype/pick_list.js
```

## Option 1: Using Git Bash or Command Prompt with Git

If you have Git installed, open Git Bash or Command Prompt and run:

```bash
# Navigate to the project directory
cd d:/C4erp-APP/c4factory

# Check current status
git status

# Add all new and modified files
git add .

# Commit with a descriptive message
git commit -m "feat: Implement Pick List-based manufacturing system

- Add editable Work Order items (c4_required_items)
- Create Pick List from Work Order with balance tracking
- Generate Stock Entries from Pick List (full and partial)
- Implement automatic Pick List status management
- Add consumed quantity tracking
- Support for scrap items in new flow
- Complete integration with hooks and patches

Closes #[issue-number]"

# Push to remote repository
git push origin main
# OR if your branch is different:
# git push origin develop
# git push origin your-branch-name
```

## Option 2: Using GitHub Desktop

1. Open GitHub Desktop
2. Select the c4factory repository
3. Review the changes in the "Changes" tab
4. Write commit message: "feat: Implement Pick List-based manufacturing system"
5. Add description with the bullet points above
6. Click "Commit to main" (or your branch name)
7. Click "Push origin"

## Option 3: Using VS Code Source Control

1. Open VS Code
2. Click on Source Control icon (Ctrl+Shift+G)
3. Review all changed files
4. Click "+" to stage all changes
5. Enter commit message in the text box
6. Click the checkmark to commit
7. Click "..." menu → Push

## Option 4: Install Git First

If Git is not installed:

1. Download Git from: https://git-scm.com/download/win
2. Install Git for Windows
3. Restart your terminal
4. Follow Option 1 instructions above

## Recommended Commit Message

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
- Added 13 new files (hooks, APIs, UI scripts, custom fields)
- Modified 5 existing files (hooks, patches)
- Created comprehensive documentation

Files Created:
- Custom field definitions for Pick List, Pick List Item, Stock Entry
- pick_list_hooks.py for validation and status management
- work_order_pick_list.py API for Pick List creation
- pick_list_stock.py API for Stock Entry creation
- work_order.js and pick_list.js for UI enhancements
- Database patches for custom fields
- Documentation (TODO.md, IMPLEMENTATION_SUMMARY.md)

Files Modified:
- work_order_hooks.py - Added required items copying and balance calculation
- stock_entry_hooks.py - Added Pick List tracking on submit/cancel
- setup_work_order_custom_fields.py - Added c4_required_items fields
- hooks.py - Registered all new hooks and patches
- pick_list.js - Added Stock Entry creation functionality

Breaking Changes: None
Backward Compatibility: Yes - Old BOM-based flow still works

Testing Required:
- Run bench migrate to apply patches
- Test complete workflow: WO → PL → SE
- Verify status updates and balance calculations
```

## After Pushing

1. Verify the push was successful by checking your repository on GitHub/GitLab
2. Create a Pull Request if working on a feature branch
3. Run `bench migrate` on your server to apply the changes
4. Test the new functionality

## Troubleshooting

**If push is rejected:**
```bash
# Pull latest changes first
git pull origin main --rebase

# Then push again
git push origin main
```

**If you need to create a new branch:**
```bash
git checkout -b feature/pick-list-manufacturing
git push -u origin feature/pick-list-manufacturing
```

**If you want to see what will be pushed:**
```bash
git diff HEAD
git log origin/main..HEAD
