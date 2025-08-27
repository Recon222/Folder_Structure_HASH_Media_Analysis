# 7-Zip Binary Download Instructions

## Required Binary: 7za.exe

### Download Steps:
1. Visit the official 7-Zip website: https://www.7-zip.org/
2. Navigate to Download section
3. Download the "7-Zip Command Line Version" 
4. Extract `7za.exe` from the downloaded archive
5. Place `7za.exe` in this `/bin/` directory
6. Verify it works by running: `.\bin\7za.exe`

### Expected Location:
```
folder_structure_application/
├── bin/
│   └── 7za.exe  ← Download this here
└── ...
```

### Verification Command:
```bash
.venv/Scripts/python.exe -c "from pathlib import Path; print('7za.exe found:', Path('bin/7za.exe').exists())"
```

### File Information:
- **Filename**: 7za.exe
- **Expected Size**: ~1-3MB
- **Version**: Latest stable (currently 23.01)
- **SHA-256**: Will be verified by the application

### Alternative Download Links:
- Official: https://www.7-zip.org/a/7z2301-extra.7z (extract 7za.exe)
- Direct (if available): https://www.7-zip.org/a/7za920.exe

### Security:
- Only download from official 7-zip.org website
- The application will verify the binary integrity on startup
- If verification fails, it will fall back to Python ZIP operations