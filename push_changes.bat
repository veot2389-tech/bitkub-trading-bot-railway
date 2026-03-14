@echo off
echo Starting git commands... > git_log.txt
git add . >> git_log.txt 2>&1
echo Staged files >> git_log.txt
git commit -m "Fix: Unified case-insensitive coin matching for layers" >> git_log.txt 2>&1
echo Committed >> git_log.txt
git push origin master >> git_log.txt 2>&1
echo Finished >> git_log.txt
