@echo off
cd /d "C:\Python\murmuration_watch_uk"
echo ================================================== >> pipeline.log
echo Run started: %DATE% %TIME% >> pipeline.log
"C:\Users\justi\AppData\Local\Python\pythoncore-3.15-64\python.exe" "src\fetch_sightings.py" >> pipeline.log 2>&1
"C:\Users\justi\AppData\Local\Python\pythoncore-3.15-64\python.exe" "src\audit_pipeline.py" >> pipeline.log 2>&1
echo Run finished: %DATE% %TIME% >> pipeline.log