@echo off

REM Check if virtual environment exists
if not exist ".\venv\deposition-detection" (
    echo Creating virtual environment...
    python -m venv .\venv\deposition-detection
    
    echo Installing requirements...
    echo This might take a while
    call .\venv\deposition-detection\Scripts\activate
    pip install -r requirements.txt
    echo Requirements successfully installed.
) else (
    echo Virtual environment already exists
)

echo Launching server...
REM Activate virtual environment
call .\venv\deposition-detection\Scripts\activate

REM Run the main script
python .\src\main.py
