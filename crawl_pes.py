import datetime
import shutil
import subprocess
import os
import json
import re
import tempfile
import requests
import platform

import log


# PE_EXTENSIONS = [".acm", ".ax", ".cpl", ".dll", ".drv", ".efi", ".exe", ".mui", ".ocx", ".scr", ".sys", ".tsp"]
PE_EXTENSIONS = [".cpl"]
UPDATES_JSON_PATH = "updates.json"
DATA_PATH = "data"
ARIA2C_APP_PATH = "tools/aria2c.exe"

class UpdateNotFound(Exception):
    pass



def listtree(path, full_paths=True, ignore_links=True):
    """ List all files in a path recursively, and add the full path to them. """
    if os.path.isfile(path):
        if ignore_links and os.path.islink(path):
            return []
        return [path]
    res = []
    for dirpath, dirnames, filenames in os.walk(path):
        for fn in filenames:
            file_path = os.path.join(dirpath, fn) if full_paths else fn
            if not ignore_links or not os.path.islink(file_path):
                res.append(file_path)
    return res


def pes_from_msu(msu_path):

    bn, dn = os.path.basename(msu_path), os.path.dirname(msu_path)
    log.info(f"Expanding {msu_path} to {os.path.join('data', bn)}__*")
    cab_dir = os.path.join(dn, "cabs")
    if not os.path.exists(cab_dir):
        os.mkdir(cab_dir)

    subprocess.getstatusoutput(f"expand -F:*.cab {msu_path} {cab_dir}")
    work_dir = os.path.join(dn, "workdir")
    if not os.path.exists(work_dir):
        os.mkdir(work_dir)

    work_list = list(filter(lambda _: _.endswith(".cab"), listtree(cab_dir)))
    done_list = []
    while len(work_list) > 0:
        cab_path = work_list.pop()
        for extension in PE_EXTENSIONS:
            sub_dir = tempfile.mkdtemp(dir=work_dir, prefix=f"{os.path.basename(cab_path)}.", suffix=f"{extension}")
            cmd = f"expand -F:*{extension} {cab_path} {sub_dir}"
            r, o = subprocess.getstatusoutput(cmd)
            if r != 0:
                log.warn(f"{cmd} failed with error code {r} and output {o}")
            else:
                total = o.splitlines()[-1]
                num_files = 0
                if " files total." in total:
                    num_files = total.replace(' files total.', '')
                log.info(f"{num_files} files collected from {cab_path} at extension {extension}")

        # handle recursive cabs
        subprocess.getstatusoutput(f"expand -F:*.cab {cab_path} {cab_dir}")
        try:
            os.remove(cab_path)
        except Exception as e:
            pass

        work_list = listtree(cab_dir)
        assert list(filter(lambda _: _.endswith(".cab"), listtree(cab_dir))) == work_list
        done_list.append(cab_path)
        work_list = list(filter(lambda _: _ not in done_list, work_list))

    for pe in listtree(work_dir):
        extension = pe.split(".")[-1]
        if f".{extension}" not in PE_EXTENSIONS:
            continue
        dst = f"{os.path.join(DATA_PATH, extension, bn)}__{os.path.basename(pe)}"
        if not os.path.exists(dst):
            os.rename(pe, dst)

    for d in [cab_dir, work_dir]:
        try:
            shutil.rmtree(d)
        except PermissionError:
            pass


def search_for_updates(search_terms):
    url = 'https://www.catalog.update.microsoft.com/Search.aspx'
    while True:
        html = requests.get(url, {'q': search_terms}).text
        if 'The website has encountered a problem' not in html:
            break
        # Retry...

    if 'We did not find any results' in html:
        raise UpdateNotFound

    assert '(page 1 of 1)' in html  # we expect only one page of results

    p = r'<a [^>]*?onclick=\'goToDetails\("([a-f0-9\-]+)"\);\'>\s*(.*?)\s*</a>'
    matches = re.findall(p, html)

    p2 = r'<input id="([a-f0-9\-]+)" class="flatBlueButtonDownload" type="button" value=\'Download\' />'
    assert [uid for uid, title in matches] == re.findall(p2, html)

    return matches


def get_update_download_url(update_uid):
    input_json = [{
        'uidInfo': update_uid,
        'updateID': update_uid
    }]
    url = 'https://www.catalog.update.microsoft.com/DownloadDialog.aspx'
    html = requests.post(url, {'updateIDs': json.dumps(input_json)}).text

    p = r'\ndownloadInformation\[\d+\]\.files\[\d+\]\.url = \'([^\']+)\';'
    matches = re.findall(p, html)
    if len(matches) != 1:
        raise Exception(f'Expected one downloadInformation item, found {len(matches)}')

    return matches[0]


def download_update(windows_version, update_kb):
    found_updates = search_for_updates(f'{update_kb} {windows_version} x64')

    filter_regex = r'\bserver\b|\bDynamic Cumulative Update\b'

    found_updates = [update for update in found_updates if not re.search(filter_regex, update[1], re.IGNORECASE)]

    if len(found_updates) != 1:
        raise Exception(f'Expected one update item, found {len(found_updates)}')

    update_uid, update_title = found_updates[0]
    assert re.fullmatch(
        rf'(\d{{4}}-\d{{2}} )?Cumulative Update (Preview )?for Windows 10 Version {windows_version} for x64-based Systems \({update_kb}\)',
        update_title), update_title

    download_url = get_update_download_url(update_uid)
    if not download_url:
        raise Exception('Update not found in catalog')

    local_dir = os.path.join('msus', windows_version, update_kb)
    if not os.path.exists(local_dir):
        os.makedirs(local_dir, exist_ok=True)

    local_filename = download_url.split('/')[-1]
    local_path = os.path.join(local_dir, local_filename)

    if os.path.isfile(local_path):
        log.info(f"Existing copy of '{local_path}' found, using it instead of downloading.")
        return local_path

    args = [ARIA2C_APP_PATH, '-x4', '-o', local_path, '--allow-overwrite=true', download_url]

    if subprocess.run(args, check=True,
                      stdout=None if log.logging_levels_ordinals[log.logging_level] < log.logging_levels_ordinals[log.WARNING] else subprocess.DEVNULL).returncode != 0:
        log.warn(f"Error while running '{' '.join(args)}'")
        return None

    return local_path




def main():
    assert platform.system() == "Windows" and "This will only work under Windows."
    assert os.path.isfile(UPDATES_JSON_PATH) and f"'{UPDATES_JSON_PATH}' missing. Use the supplied one or download using https://github.com/m417z/winbindex/blob/gh-pages/data/upd01_get_list_of_updates.py"
    assert os.path.isfile(ARIA2C_APP_PATH) and "tools/aria2c.exe needed for downloading MSUs"

    log.logging_level = log.INFO

    # downloaded = filter(lambda _: _.endswith(".msu"), listtree("manifests"))  # TODO: remove when using download_msus

    for extension in PE_EXTENSIONS:
        os.makedirs(os.path.join(DATA_PATH, extension.replace(".", "")), exist_ok=True)

    with open(UPDATES_JSON_PATH, "r") as fp:
        updates = json.load(fp)

    for windows_version in dict(updates):
        log.info(f'Processing Windows version {windows_version}')

        for update_kb in dict(updates[windows_version]):
            try:
                log.info(f'[{update_kb}] Downloading update')
                local_path = download_update(windows_version, update_kb)
                log.info(f"Downloaded to {local_path}")
                pes_from_msu(local_path)

            except UpdateNotFound:
                # Only treat as an error if the update is recent. If the update is old,
                # only show a warning, since old updates are removed from the update catalog
                # with time.
                a_while_ago = (datetime.date.today() - datetime.timedelta(days=90)).isoformat()
                if updates[windows_version][update_kb]['releaseDate'] > a_while_ago:
                    log.error(f'[{update_kb}] ERROR: Update wasn\'t found')
                else:
                    log.warn(
                        f'[{update_kb}] WARNING: Update wasn\'t found, it was probably removed from the update catalog')
                    del updates[windows_version][update_kb]
                    with open(msu_json_path, "w") as fp:
                        json.dump(updates, fp, indent=1)
            except Exception as e:
                log.error(f'[{update_kb}] ERROR: Failed to process update')
                log.error(f'[{update_kb}]        ' + str(e))



if __name__ == '__main__':
    main()
