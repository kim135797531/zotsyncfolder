import os
import time
from collections import defaultdict
import tempfile
import xml.etree.ElementTree as ET

import zipfile
import configparser
import json
import hashlib
from shutil import copyfile

from networks import download, prefix, headers, get_last_modified_version, download_lists, list_to_dict, upload
from backend import convert_zotero_item_to_zsf_item, generate_original_file_path, generate_new_file_path, is_real_item, \
    is_real_attachment
from webdav3.client import Client

parser = configparser.ConfigParser()
parser.read('zotsyncfolder.conf')
config = parser['DEFAULT']

user_id = config['user_id']
api_key = config['api_key']
json_folder = config['json_folder']
output_folder = config['output_folder']
zotero_folder = config['zotero_folder']
target_ext_list = config['target_ext_list']
load_from_cache = config.getboolean('load_from_cache')
modified_diff_threshold_seconds = config.getint('modified_diff_threshold_seconds')
webdav_hostname = config['webdav_hostname']
webdav_login = config['webdav_login']
webdav_password = config['webdav_password']
webdav_zotero_url = config['webdav_zotero_url']


options = {
    'webdav_hostname': webdav_hostname,
    'webdav_login':    webdav_login,
    'webdav_password': webdav_password,
    'disable_check': True
}
webdav_client = Client(options)

global_metadata_json = f'{json_folder}/global_metadata.json'
collection_metadatas_json = f'{json_folder}/collection_metadatas.json'
item_metadatas_json = f'{json_folder}/item_metadatas.json'
notifier_metadatas_json = f'{json_folder}/notifier_metadatas.json'


# 일단 파일 변경 시각 보고, 뭔가 수상하면 md5 비교해서 최종적으로 판단하기
def get_changed_files(collection_metadatas, item_metadatas):
    ret = []
    for item_key, item_metadata in item_metadatas.items():
        if 'attachment_keys' in item_metadata:
            for attachment_key in item_metadata['attachment_keys']:
                attachment = item_metadatas[attachment_key]
                original_file_path = generate_original_file_path(zotero_folder, attachment)

                if not os.path.exists(original_file_path):
                    continue

                if 'key' not in item_metadata:
                    continue

                for collection_key in item_metadata['collections']:
                    collection = collection_metadatas[collection_key]
                    new_file_path = generate_new_file_path(collection, attachment)

                    # 새 파일&json기록의 크기와, 새 파일&실제의 크기가 다르면
                    # 새 파일&json기록의 md5와, 새 파일&실제의 md5 검사로 심층 분석.
                    # 이미 오리지날하고는 관계 없어졌으니, 오리지날은 무시해도 될 듯.
                    new_file_modified = os.path.getmtime(new_file_path)
                    new_modified_record = attachment['new_modified']
                    if abs(new_file_modified - new_modified_record) > modified_diff_threshold_seconds:
                        new_file_md5_record = attachment['md5']
                        new_file_md5 = hashlib.md5(open(new_file_path, 'rb').read()).hexdigest()
                        if new_file_md5 != new_file_md5_record and new_file_modified > new_modified_record:
                            # 뭔가 바뀌었고, 아이패드쪽이 최신이다.
                            # TODO: 일단 프로그램 불안정하니 백업 만들기??
                            ret.append(dict(
                                collection_key=collection_key,
                                item_key=item_key,
                                attachment_key=attachment_key
                            ))
                    """
                    original_file_modified = os.path.getmtime(original_file_path)
                    new_file_modified = os.path.getmtime(new_file_path)
                    original_modified_record = attachment['original_modified']
                    new_modified_record = attachment['new_modified']

                    if abs(original_file_modified - original_modified_record) > modified_diff_threshold_seconds:
                        if abs(original_file_modified - new_file_modified) <= modified_diff_threshold_seconds:
                            print('아마 이 프로그램에서 업뎃한 파일을 zotero가 zotero 로컬 저장소에도 반영한듯. 이건 그냥 고친다.')
                            attachment['original_modified'] = new_file_modified
                        else:
                            print('json상의 파일 기록과 zotero 로컬 저장소와의 차이 심함')
                            print('여기서 md5검사해서, 걍 zotero 로컬 저장소 측이 느린건지 보자. 원래 로컬 저장소하고 전혀 관련 없어야 함')

                            original_file_md5 = hashlib.md5(open(original_file_path, 'rb').read()).hexdigest()
                            new_file_md5 = hashlib.md5(open(new_file_path, 'rb').read()).hexdigest()

                    elif abs(new_file_modified - new_modified_record) > modified_diff_threshold_seconds:
                        ret.append(dict(
                            collection_key=collection_key,
                            item_key=item_key,
                            attachment_key=attachment_key
                        ))
                    """

    return ret


# zotsyncfolder에서 업데이트된 (아이패드에서 메모한) 항목을 zotero에 알리고 업데이트
def upload_changed_file(collection_metadatas, item_metadatas, keyset):
    tempdir = tempfile.TemporaryDirectory()

    collection = collection_metadatas[keyset['collection_key']]
    attachment = download(f"{prefix}/items/{keyset['attachment_key']}", headers).json()
    attachment_file = generate_new_file_path(collection, attachment['data'])
    attachment_file_name = attachment["data"]["filename"]
    attachment_file_size = os.path.getsize(attachment_file)
    attachment_file_mtime = int(os.path.getmtime(attachment_file) * 1000)
    attachment_file_md5 = hashlib.md5(open(attachment_file, 'rb').read()).hexdigest()

    # 서버에서 다운로드하자
    webdav_client.download_sync(
        remote_path=f"{webdav_zotero_url}/{keyset['attachment_key']}.prop",
        local_path=f"{tempdir.name}/{keyset['attachment_key']}_original.prop"
    )
    webdav_client.download_sync(
        remote_path=f"{webdav_zotero_url}/{keyset['attachment_key']}.zip",
        local_path=f"{tempdir.name}/{keyset['attachment_key']}_original.zip"
    )
    zipfile.ZipFile(f"{tempdir.name}/{keyset['attachment_key']}_original.zip").extractall(f"{tempdir.name}")
    server_file_name = attachment["data"]["filename"]
    server_file = f"{tempdir.name}/{server_file_name}"
    # server_file_size = os.path.getsize(server_file)
    tree = ET.parse(f"{tempdir.name}/{keyset['attachment_key']}_original.prop")
    # server_file_mtime = tree.find('mtime').text
    server_file_md5 = hashlib.md5(open(server_file, 'rb').read()).hexdigest()

    auth_headers = headers.copy()
    auth_headers['Content-Type'] = 'application/x-www-form-urlencoded'
    auth_headers['If-Match'] = server_file_md5

    auth_data = dict(
        md5=attachment_file_md5,
        filename=attachment_file_name,
        filesize=attachment_file_size,
        mtime=attachment_file_mtime,
    )

    url = f'{prefix}/items/{attachment["key"]}/file'
    auth_result = upload(url, auth_headers, auth_data)

    if auth_result.status_code == 200:
        auth_result = auth_result.json()
    else:
        print(f'auth 실패! {auth_result.status_code}')
        auth_result = dict(exists=1)

    if 'exists' in auth_result:
        # 이미 업로드 완료됨 (수행할 작업 없음)
        pass
    else:
        # Zotero 공식 파일 저장소에 업로드
        with open(attachment_file, 'rb') as attachment_file_binary:
            auth_headers['Content-Type'] = auth_result['contentType']
            binary_data = attachment_file_binary.read()
            binary_data = str.encode(auth_result['prefix']) + binary_data + str.encode(auth_result['suffix'])
            result = upload(auth_result['url'], auth_headers, binary_data)

        # WebDav 서버에 업로드
        zf = zipfile.ZipFile(f"{tempdir.name}/{keyset['attachment_key']}_new.zip", 'w')
        zf.write(attachment_file, attachment_file_name)
        zf.close()

        new_prop = open(f"{tempdir.name}/{keyset['attachment_key']}_new.prop", "w")
        new_prop.write(f'<properties version="1"><mtime>{attachment_file_mtime}</mtime><hash>{attachment_file_md5}</hash></properties>')
        new_prop.close()
        webdav_client.upload_sync(
            remote_path=f"{webdav_zotero_url}/{keyset['attachment_key']}.zip",
            local_path=f"{tempdir.name}/{keyset['attachment_key']}_new.zip"
        )
        webdav_client.upload_sync(
            remote_path=f"{webdav_zotero_url}/{keyset['attachment_key']}.prop",
            local_path=f"{tempdir.name}/{keyset['attachment_key']}_new.prop"
        )

        auth_headers['Content-Type'] = 'application/x-www-form-urlencoded'
        auth_data = dict(
            upload=auth_result['uploadKey']
        )
        result = upload(url, auth_headers, auth_data)

        if result.status_code == 204:
            print(attachment_file_name)
        else:
            print(result)
            print('업로드 실패! 아마 동시에 동기화해서 깨진듯. 일단 걍 리턴함')
            return

        # TODO: 보고한 것은 보고했다고 업데이트 하는거 여기서 해도 되나
        item_metadatas[keyset['attachment_key']]['new_modified'] = (attachment_file_mtime / 1000)
        item_metadatas[keyset['attachment_key']]['md5'] = attachment_file_md5
        attachment_updated_info = download(f"{prefix}/items/{keyset['attachment_key']}", headers).json()
        item_metadatas[keyset['attachment_key']]['version'] = int(attachment_updated_info['version'])

    tempdir.cleanup()


def overwrite_one_file(collection_metadatas, item_metadatas, attachment):
    parent_key = attachment['data']['parentItem']
    attachment_key = attachment['key']

    # 근데 아이패드 파일에 바뀐거도 남아있는데, 아직 업뎃 안한거 남아있으면??
    # 그럼, 아이패드 파일의 md5하고, 내가 갖고 있는 캐시의 md5하고도 다르겠지?
    for collection_key in item_metadatas[parent_key]['collections']:
        collection = collection_metadatas[collection_key]
        new_file_path = generate_new_file_path(collection, attachment['data'])
        if not os.path.exists(new_file_path):
            continue
        new_file_md5 = hashlib.md5(open(new_file_path, 'rb').read()).hexdigest()
        if item_metadatas[attachment['key']]['md5'] != new_file_md5:
            # TODO: 어라 아직 아이패드에 동기화 안한게 있네요. 강종함
            print('어라 아직 아이패드에 동기화 안한게 있네요. 강종함')
            exit(1)

    tempdir = tempfile.TemporaryDirectory()
    webdav_client.download_sync(
        remote_path=f"{webdav_zotero_url}/{attachment_key}.zip",
        local_path=f"{tempdir.name}/{attachment_key}_original.zip"
    )
    zipfile.ZipFile(f"{tempdir.name}/{attachment_key}_original.zip").extractall(f"{tempdir.name}")
    server_file_name = attachment["data"]['filename']
    server_file = f"{tempdir.name}/{server_file_name}"
    server_file_md5 = hashlib.md5(open(server_file, 'rb').read()).hexdigest()

    zotero_db_md5 = attachment['data']['md5']
    if zotero_db_md5 is None:
        print('새로 업뎃된 파일에 md5 없음. 아직 생성중인거같음')
        return
    elif zotero_db_md5 != server_file_md5:
        # TODO: zotero 정보상 최신 파일이랑 새로 다운받은 파일이랑 md5가 다르다? 강종함
        print('zotero 정보상 최신 파일이랑 새로 다운받은 파일이랑 md5가 다르다? 강종함')
        tempdir.cleanup()
        exit(1)

    for collection_key in item_metadatas[parent_key]['collections']:
        collection = collection_metadatas[collection_key]
        new_file_path = generate_new_file_path(collection, attachment['data'])
        copyfile(server_file, new_file_path)

        # original_modified는 여기는 zotero 로컬이랑 관련 없어서 할 필요는 없지만 캐싱을 위해 일단 넣음
        # original_file_path = generate_original_file_path(zotero_folder, attachment['data'])
        # original_modified = os.path.getmtime(original_file_path) if os.path.exists(original_file_path) else -1
        # item_metadatas[attachment_key]['original_modified'] = original_modified
        item_metadatas[attachment_key]['new_modified'] = os.path.getmtime(new_file_path)
    tempdir.cleanup()


def update_last_modified_version(global_metadata):
    global_metadata['last_modified_version'] = get_last_modified_version()
    f = open(global_metadata_json, 'w')
    print(json.dumps(global_metadata, indent=4), file=f)
    f.close()


def pull_changed_list_from_zotero(global_metadata, collection_metadatas, item_metadatas):
    modified_items = download_lists(f"{prefix}/items?since={global_metadata['last_modified_version']}", headers)

    # 먼저 item들에 대해 확실히 끝냄 (collection을 알아야 나중에 폴더에 넣을 수 있음)
    for item in modified_items:
        if is_real_item(item):
            item_key = item['key']
            if item_key in item_metadatas and 'version' in item_metadatas[item_key]:
                # 기존에 있던 항목
                if set(item_metadatas[item_key]['collections']) != set(item['data']['collections']):
                    # TODO: 컬렉션 정보 바뀜!! 아직 지원 안함. 프로그램 강종함.
                    print("컬렉션 정보 바뀜!! 아직 지원 안함. 프로그램 강종함.")
                    exit(1)
                item_metadatas[item_key]['version'] = item['version']
            else:
                # 새로 추가된 항목
                item_metadatas[item_key]['key'] = item['key']
                item_metadatas[item_key]['version'] = item['version']
                item_metadatas[item_key]['collections'] = item['data']['collections']

    # item들 끝나면 attachment들에 대해 돌음
    for item in modified_items:
        if is_real_attachment(item, target_ext_list):
            attachment_key = item['key']
            if attachment_key in item_metadatas and 'version' in item_metadatas[attachment_key]:
                # 기존에 있던 항목
                parent_key = item['data']['parentItem']
                if int(item_metadatas[attachment_key]['version']) < int(item['data']['version']):
                    print("있던 PDF인데, 아이패드에서 바뀐게 아니라 원격에서 바뀜. 새로 다운받자")
                    overwrite_one_file(collection_metadatas, item_metadatas, item)

                item_metadatas[attachment_key]['version'] = item['version']
                item_metadatas[attachment_key]['filename'] = item["data"]['filename']
                item_metadatas[attachment_key]['md5'] = item["data"]['md5']
            else:
                # 새로 추가된 항목
                parent_key = item['data']['parentItem']
                item_metadatas[attachment_key]['key'] = item['key']
                item_metadatas[attachment_key]['version'] = item['version']
                item_metadatas[attachment_key]['filename'] = item["data"]['filename']
                item_metadatas[attachment_key]['md5'] = item["data"]['md5']
                item_metadatas[parent_key]['attachment_keys'].append(item['key'])
                overwrite_one_file(collection_metadatas, item_metadatas, item)
        else:
            pass

    if len(modified_items) > 0:
        f = open(item_metadatas_json, 'w')
        print(json.dumps(item_metadatas, indent=4), file=f)
        f.close()
        update_last_modified_version(global_metadata)
        print(f'[{time.ctime()}] Zotero의 DB 갱신 사항 **업뎃 완료**')
    else:
        print(f'[{time.ctime()}] Zotero의 DB 갱신 사항 변화 없음')


if __name__ == "__main__":
    global_metadata = json.load(open(global_metadata_json, 'r'))

    collection_metadatas = json.load(open(collection_metadatas_json, 'r'))
    collection_metadatas = defaultdict(dict, collection_metadatas)

    item_metadatas_prepare = json.load(open(item_metadatas_json, 'r'))
    item_metadatas = defaultdict(lambda: defaultdict(list))
    for parent_key, parent_values in item_metadatas_prepare.items():
        for child_key, child_values in parent_values.items():
            item_metadatas[parent_key][child_key] = child_values

    if os.path.exists(notifier_metadatas_json):
        notifier_metadatas = json.load(open(notifier_metadatas_json, 'r'))
    else:
        notifier_metadatas = {
            'last_modified_version': global_metadata['last_modified_version']
        }
        f = open(notifier_metadatas_json, 'w')
        print(json.dumps(notifier_metadatas, indent=4), file=f)
        f.close()

    while True:
        # zotero 파일 변화 감지 시작 ============================================
        notifier_metadatas = json.load(open(notifier_metadatas_json, 'r'))
        received_update_signal = int(global_metadata['last_modified_version']) < int(notifier_metadatas['last_modified_version'])
        if received_update_signal:
            pull_changed_list_from_zotero(global_metadata, collection_metadatas, item_metadatas)
            notifier_metadatas = {
                'last_modified_version': global_metadata['last_modified_version']
            }
            f = open(notifier_metadatas_json, 'w')
            print(json.dumps(notifier_metadatas, indent=4), file=f)
            f.close()
        # zotero 파일 변화 감지 끝 ============================================

        # zotsyncfolder 파일 변화 감지 시작 ============================================
        update_item_keysets = get_changed_files(collection_metadatas, item_metadatas)

        if len(update_item_keysets) > 10:
            print("변경이 10개 이상이라니! 이건 뭔가 잘못됐다.")
            break

        for update_item_keyset in update_item_keysets:
            upload_changed_file(collection_metadatas, item_metadatas, update_item_keyset)

        if len(update_item_keysets) > 0:
            f = open(item_metadatas_json, 'w')
            print(json.dumps(item_metadatas, indent=4), file=f)
            f.close()
            print(f'[{time.ctime()}] 아이패드의 갱신 사항 **업뎃 완료**')
        else:
            print(f'[{time.ctime()}] 아이패드의 갱신 사항 변화 없음')

        # zotsyncfolder 파일 변화 감지 끝 ============================================
        time.sleep(60)
