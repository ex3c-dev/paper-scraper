import os
from tika import parser # pip install tika
import re
import json
from pathlib import Path
from scholarly import scholarly
from scholarly import ProxyGenerator
import pandas as pd
import argparse


def remove_file_extension(file):    
    return Path(file).resolve().stem

def get_files(folder):
    import os
    os.chdir(folder)
    files = os.listdir()
    files = [x for x in files if x.endswith(".pdf")]
    return files

def create_txt_files(path, filename):
    KILL_KEY = 'esc'
    read_path = str(path + "/" + filename)
    write_path = str(path + remove_file_extension(filename)) + ".txt"
    write_path_meta = str(path + remove_file_extension(filename)) + ".meta.json"
    overwrite_file = os.path.exists(write_path)
    

    raw = parser.from_file(str(path + "/" + filename))
    start = raw['content'].find('References')
    end = raw['content'].find('About the Authors')

    to_write = raw['content'][start:end]
    
    
    with open(write_path, "w", encoding="utf-8") as f:
        f.write(to_write)
        f.close()

    with open(write_path_meta, "w", encoding="utf-8") as f:
        json_str = json.dumps(raw['metadata'])
        f.write(json_str)
        f.close()
        
    return raw['status']

def parse_file(path, filename, footer=[]):
    with open(str(path + remove_file_extension(filename)) + ".txt", 'r', encoding="utf-8") as f:
        to_write = []
        tmp = ""
        last_line = ""
        line_no = 1
        first_line = True
        regexp = re.compile(r'\([0-9]{4}[a-z]\)')
        regexp2 = re.compile(r'\([0-9]{4}\)')
        for line in f:
            skip_line = False
            for keyword in footer:
                if line.__contains__(keyword):
                    skip_line = True
            if not skip_line:
                if not first_line and len(last_line) <= 1:
                    ## Make cut here and write to csv
                    to_write.append(tmp + "\n")
                    tmp = ""
                    tmp += line.replace("\n", "")
                    last_line = ""
                    line_no = 1
                    first_line = True
                else:
                    tmp += line.replace("\n", "")
                    first_line = False
            last_line = line
            line_no += 1
        write_to_bib(path, filename, to_write)
        f.close()

def write_to_bib(path, filename, to_write):
    f = open(path + remove_file_extension(filename) + ".bib", 'w', encoding="utf-8")
    for row in to_write:
        f.write(row)
    f.close()

def read_bib_files(folder, file_ending):
    import os
    os.chdir(folder)
    files = os.listdir()
    files = [x for x in files if x.endswith(file_ending)]
    return files

def create_config():
    parser = argparse.ArgumentParser(description="Parse scientific papers for references and scrape google scholar for the results")
    parser.add_argument('--command', dest='command', const='scrape', default='extract', nargs='?', help='Either "scrape" or "extract"')
    parser.add_argument('--folder', dest='folder', default=os.getcwd() + "\\papers\\", nargs='?',help='Specify the folder to look for documents')
    parser.add_argument('--api', dest='api', default=["free"], nargs=2, help='API to use for scraping. Default is free proxies. ScraperAPI is supported but api key needs to be provided.')
    parser.add_argument('--ignore', dest='ignore', default=[], nargs='+',help='List of words to ignore (footer sentence for example)')
    parser.add_argument('--continue', dest='cont', default=None, nargs=1,help='Continue working on a file specified')
    return parser.parse_args()

def scrape_scholar(folder, files):
    for file in files:
        results = []
        fails = []
        with open(folder + file, 'r', encoding="utf-8") as f:
            count = 1
            for line in f:
                try:
                    print(count, " searching: " , line[0:75], "...")
                    count += 1
                    search_query = scholarly.search_pubs(line.replace("\n", ""))
                    data = next(search_query)
                    if data:
                        results.append({
                            'title': data['bib']['title'],
                            'authors': data['bib']['author'],
                            'abstract': data['bib']['abstract'],
                            'citations': data['num_citations'],
                        })
                    else:
                        fails.append(line)
                except Exception:
                    print("\tSearch request failed (Google die puta)")
                    fails.append(line)
                    pass
            
            # Write successful data
            df = pd.DataFrame.from_dict(results)
            df.to_csv(folder + file + '.csv', mode='a', encoding='utf-8', index=False)

            #Write failed data
            print("Missing: ", len(fails), " - to continue trying append continue option")
            f = open(folder + file + '.fail', 'w', encoding="utf-8")
            for row in fails:
                f.write(row)
            f.close()

def main():
    args = create_config()
    if args.command == "extract":
        folder = args.folder
        if not folder.endswith("/") or not folder.endswith("\\"):
            folder += "\\"
        ignore_params = args.ignore
        files = get_files(folder)

        for f in files:
            status = create_txt_files(folder, f)
            if status == 200:
                parse_file(folder, f, footer=ignore_params)
        
        print("Extraction complete! Please check .bib files manually before scraping!")

    elif args.command == "scrape":
        print("Scraping")
        folder = args.folder
        if not folder.endswith("/") or not folder.endswith("\\"):
            folder += "\\"
        files = None
        if args.cont:
            files = args.cont
        else:
            files = read_bib_files(folder, ".bib")
        
        # Setup proxies for the google search
        pg = ProxyGenerator()
        if args.api[0] != "free":
            pg.ScraperAPI(args.api[1], country_code=None, premium=False, render=False)
        else:
            pg.FreeProxies()
        scholarly.use_prox(pg)

        scrape_scholar(folder, files)

if __name__ == "__main__":
    main()