# PowerShell Script to Create Pull Request for Pick List Manufacturing Feature
# This script will guide you through creating a PR even if Git is not in PATH

Write-Host "=== C4Factory Pick List Manufacturing - Pull Request Creator ===" -ForegroundColor Cyan
Write-Host ""

# Function to check if Git is available
function Test-GitAvailable {
    $gitPaths = @(
        "git",
        "C:\Program Files\Git\bin\git.exe",
        "C:\Program Files (x86)\Git\bin\git.exe",
        "$env:LOCALAPPDATA\Programs\Git\bin\git.exe"
    )
    
    foreach ($gitPath in $gitPaths) {
        try {
            $null = & $gitPath --version 2>&1
            return $gitPath
        } catch {
            continue
        }
    }
    return $null
}

# Check for Git
$gitCommand = Test-GitAvailable

if ($null -eq $gitCommand) {
    Write-Host "❌ Git is not installed or not found in common locations." -ForegroundColor Red
    Write-Host ""
    Write-Host "Please choose an option:" -ForegroundColor Yellow
    Write-Host "1. Install Git from https://git-scm.com/download/win" -ForegroundColor White
    Write-Host "2. Use GitHub Desktop (https://desktop.github.com/)" -ForegroundColor White
    Write-Host "3. Use VS Code Source Control (Ctrl+Shift+G)" -ForegroundColor White
    Write-Host ""
    Write-Host "After installing Git, run this script again or follow GIT_PUSH_INSTRUCTIONS.md" -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ Git found at: $gitCommand" -ForegroundColor Green
Write-Host ""

# Set Git command alias
Set-Alias -Name git -Value $gitCommand -Scope Script

# Get current branch
Write-Host "📋 Checking current Git status..." -ForegroundColor Cyan
$currentBranch = & git rev-parse --abbrev-ref HEAD 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Error: Not a git repository or git command failed" -ForegroundColor Red
    Write-Host "Please ensure you're in the correct directory: d:\C4erp-APP\c4factory" -ForegroundColor Yellow
    exit 1
}

Write-Host "Current branch: $currentBranch" -ForegroundColor White
Write-Host ""

# Create new branch
$newBranch = "blackboxai/pick-list-manufacturing-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
Write-Host "🌿 Creating new branch: $newBranch" -ForegroundColor Cyan

& git checkout -b $newBranch

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to create branch" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Branch created successfully" -ForegroundColor Green
Write-Host ""

# Show status
Write-Host "📊 Git Status:" -ForegroundColor Cyan
& git status --short

Write-Host ""

# Stage all changes
Write-Host "➕ Staging all changes..." -ForegroundColor Cyan
& git add .

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to stage changes" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Changes staged successfully" -ForegroundColor Green
Write-Host ""

# Create commit
$commitMessage = @"
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

Testing Required:
- Run bench migrate to apply patches
- Test complete workflow: WO → PL → SE
- Verify status updates and balance calculations
"@

Write-Host "💬 Creating commit..." -ForegroundColor Cyan
& git commit -m $commitMessage

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to create commit" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Commit created successfully" -ForegroundColor Green
Write-Host ""

# Push to remote
Write-Host "🚀 Pushing to remote repository..." -ForegroundColor Cyan
& git push -u origin $newBranch

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to push to remote" -ForegroundColor Red
    Write-Host "You may need to authenticate or check your remote configuration" -ForegroundColor Yellow
    Write-Host "Try running: git push -u origin $newBranch" -ForegroundColor White
    exit 1
}

Write-Host "✅ Pushed to remote successfully" -ForegroundColor Green
Write-Host ""

# Check if gh CLI is available
$ghCommand = Get-Command gh -ErrorAction SilentlyContinue

if ($null -eq $ghCommand) {
    Write-Host "⚠️  GitHub CLI (gh) not found" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "To create a Pull Request, you can:" -ForegroundColor White
    Write-Host "1. Install GitHub CLI: winget install GitHub.cli" -ForegroundColor Cyan
    Write-Host "2. Or visit: https://github.com/YOUR_USERNAME/c4factory/pull/new/$newBranch" -ForegroundColor Cyan
    Write-Host "3. Or use GitHub Desktop" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "✅ Your changes have been pushed to branch: $newBranch" -ForegroundColor Green
    exit 0
}

# Create Pull Request using gh CLI
Write-Host "📝 Creating Pull Request..." -ForegroundColor Cyan

$prTitle = "feat: Implement Pick List-based manufacturing system"
$prBody = @"
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
- [ ] Run \`bench migrate\` to apply patches
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
"@

& gh pr create --title $prTitle --body $prBody --base main

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to create Pull Request via gh CLI" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please create the PR manually:" -ForegroundColor Yellow
    Write-Host "Visit: https://github.com/YOUR_USERNAME/c4factory/pull/new/$newBranch" -ForegroundColor Cyan
    exit 1
}

Write-Host ""
Write-Host "✅ Pull Request created successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "🎉 All done! Your changes have been pushed and a PR has been created." -ForegroundColor Cyan
