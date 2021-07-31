# Crawl-Labeled-PE
Crawl labeled Portable Exe files from Microsoft Cabs. Retrieves ~600K files, that weigh 300GB. Takes a while to finish but files are retrieved incrementally. Only works on Windows.

This work builds upon this great tool: https://github.com/m417z/winbindex

Note: The tool does not retrieve files that are updated using diff patching. Read more about diff patching here: https://m417z.com/Introducing-Winbindex-the-Windows-Binaries-Index/ 

## Usage
```
python3 crawl_pes.py
```
