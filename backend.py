# 일렬로 내려오는 Zotero 데이터에서 트리형태를 뽑아내기
def build_key_tree(nodes):
    tree = {}
    build_key_tree_recursive(tree, False, nodes)
    return tree


# 일렬로 내려오는 Zotero 데이터에서 트리형태를 뽑아내기
def build_key_tree_recursive(tree, parent, nodes):
    children = [n for n in nodes.values() if n['data']['parentCollection'] == parent]
    for child in children:
        tree[child['key']] = {}
        build_key_tree_recursive(tree[child['key']], child['key'], nodes)


# collection 폴더 경로 문자열 생성
def set_collection_metadata(key_tree, nodes, current_path, result):
    for key, childs in key_tree.items():
        node = nodes[key]
        zsf_full_path = f"{current_path}/{node['data']['name']}"
        result[key]['key'] = key
        result[key]['version'] = node['version']
        result[key]['zsf_full_path'] = zsf_full_path
        set_collection_metadata(childs, nodes, zsf_full_path, result)


def convert_zsf_collection_to_zotero_collection(file_path):
    pass


# asdf.pdf -> asdf__ABCDEFGH__.pdf
def convert_zotero_item_to_zsf_item(item):
    collection_file_key = item["key"]
    collection_file_filename, ext = item['filename'].rsplit('.', 1)
    return f"{collection_file_filename}__{collection_file_key}__.{ext}"


# asdf__ABCDEFGH__.pdf -> (ABCDEFGH, asdf, pdf)
def convert_zsf_item_to_zotero_item(file_path):
    item_filename__key__, ext = file_path.rsplit('.', 1)
    item_filename, key, _ = item_filename__key__.rsplit('__', 2)
    return key, item_filename, ext


# zotero local file full path
def generate_original_file_path(zotero_folder, attachment):
    attachment_key = attachment['key']
    filename = attachment['filename']
    return f'{zotero_folder}/storage/{attachment_key}/{filename}'


# zotsyncfolder file full path
def generate_new_file_path(collection, attachment):
    collection_zsf_full_path = collection['zsf_full_path']
    attachment_zsf_full_path = convert_zotero_item_to_zsf_item(attachment)
    new_file_path = f'{collection_zsf_full_path}/{attachment_zsf_full_path}'

    return new_file_path


# Zotero item인가? Zotero attachment면 false
# TODO: 편의상 collection 정보가 있는 것만 item 취급 = 컬렉션에 안 들은 item은 무시
def is_real_item(item):
    return 'collections' in item['data'] and \
           len(item['data']['collections']) > 0


# Zotero attachment이고 pdf 갖고 있는가? Zotero item이면 false
def is_real_attachment(item, target_ext_list):
    ext = ''
    if 'filename' in item['data']:
        _, ext = item['data']['filename'].rsplit('.', 1)

    return 'filename' in item['data'] and \
            'linkMode' in item['data'] and \
           item['data']['linkMode'] in ['imported_file', 'imported_url'] and \
           ext.lower() in target_ext_list
