// 실행하기
// npm install zotero
// npm install configparser
// node zotero_notifier.js

var fs = require('fs');
var Zotero = require('zotero');
var assert = require('assert');
const ConfigParser = require('configparser');

const config = new ConfigParser();
config.read('zotsyncfolder.conf');
var user_id = config.get('DEFAULT', 'user_id');
var api_key = config.get('DEFAULT', 'api_key');
var json_folder = config.get('DEFAULT', 'json_folder');
var metadatas_file_path = json_folder + '/notifier_metadatas.json';

var lib = new Zotero({ user: user_id, key: api_key});
var stream = new Zotero.Stream({ apiKey: api_key });
lib.client.persist = true;
var client = lib.client;

assert(lib instanceof Zotero.Library);
assert(client instanceof Zotero.Client);

var notifier_data = {last_modified_version: -1};

var datetime = new Date();
stream.on('topicUpdated', function (data) {
    notifier_data['last_modified_version'] = data.version;
    fs.writeFile(metadatas_file_path, JSON.stringify(notifier_data), 'utf8', function(err){
        if(err) throw err;
    });
    var datetime = new Date();
    console.log(datetime + ' Last version sync requested: ' + data.version);
});
console.log('Zotero notifier started.');
