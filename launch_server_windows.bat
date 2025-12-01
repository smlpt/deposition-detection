@echo off

REM Check if virtual environment exists
if not exist ".\venv\deposition-detection\Scripts\activate.bat" (
    echo Creating virtual environment...
    
    REM Use py launcher to specify version
    py -3.10 -m venv .\venv\deposition-detection
    
    if errorlevel 1 (
        echo Failed to create virtual environment.
        echo We are using Python 3.10 here for compatibility reasons. Make sure it is installed on your system!
        exit /b 1
    )
    
    echo Installing requirements...
    echo This might take a while
    call .\venv\deposition-detection\Scripts\activate.bat
    pip install -r requirements.txt
    
    if errorlevel 1 (
        echo Failed to install requirements
        exit /b 1
    )
    
    echo Requirements successfully installed.
) else (
    echo Virtual environment already exists
)

echo Launching server...
REM Activate virtual environment
call .\venv\deposition-detection\Scripts\activate

REM Run the main script
python .\src\main.py
