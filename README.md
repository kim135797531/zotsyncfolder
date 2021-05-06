# ZotSyncFolder

Zotero <-> 컬렉션 구조와 같은 파일 구조 생성 <-> 원격 기기 (아이패드 등)

Zotero <-> Create a file structure (same as collection tree) <-> Remote device (iPad)

## 면책 조항 (Disclaimer)

* 한국어
  * 동기화 과정에 파일 날아가도 내 책임 아님
  * 나만 쓰려고 만든거라 유지보수 요청 안 받음
  * 나만 쓰려고 만든거라 실행설명 요청 안 받음
  * 코드에 욕이 난무하고 복붙의 흔적이 많고 if문 떡칠인건 대충 만들어서 그런거니 무시 ㄱ
  * Zotero 동기화 버튼은 자주자주 눌러줍시다
* 영어
  * I don't care if you lost your libraries, files etc.
  * I don't accept the fix requests.
  * I don't accept the explanation requests.
  * Plz ignore the code quality (many of if-statements, TODO, bad words..)
  * and please click the sync button of Zotero as many as possible

## 왜 만들었는가?

서지관리 프로그램인 Zotero는 원격 서버로 WebDAV를 지정할 수 있어, 
개인 WebDAV 저장소를 운영한다면 사실상 무제한 공짜이다.

잘 쓰던 도중 컴퓨터에서 논문을 넣고 아이패드에서 보고 싶어졌는데
대안들이 뭔가 다들 나사 하나씩 빠져서 너무 불편했다:

* Zotero 파일 폴더를 직접 까봐도 파일들이 원래 이름이 아니라 Zotero 내부 key로 바꿔어 
있어서 해독 불가
* 아이패드용 Zotero앱인 PaperShip은 유료인데다가, 최신 iOS에서는 앱 결제해도 필기 안
되고, 무엇보다 내가 원래 쓰던 Documents 앱 같은데에서 열 수가 없다.
* Endnote, Mendeley는 돈 없어서 못 씀 ㅠㅠ

2년 넘게 일단 서지관리 프로그램에 넣고 -> 그 pdf 파일을 복사해서 아이패드에 넣고 ->
필기하고 -> 필기된 pdf 파일을 다시 서지관리 프로그램에 업데이트하고

당연히 넣기도 귀찮고 업데이트도 귀찮고 파편화도 생기고 개판이었다.

그래서 만들었다. **ZotSyncFolder**

## 왜 ZotFile 안 쓰나? (Why not ZotFile?)

내가 잘 모르는건가 싶기도 한데...
* ZotFile은 라이브러리 전체 단위의 동기화가 안 된다. (컬렉션 단위의 동기화)
* 아이패드에서 주석 달고나서 다시 Zotero에서 가져오기 눌러야된다. 귀찮다.
* 여하튼 옵션이 많다. 걍 ui도 필요 없고 완전히 백그라운드에서 동작시키고 싶다

Maybe I just ain't used to them but...
* ZotFile didn't synchronize the entire library. (Synchronization of each collection)
* Had to click import button again after I annotated in the iPad. annoooooooooooying
* I don't need so many options and UI! I just want to work everything in background.

## 준비물

* 개인 WebDAV서버
* WebDAV에 연동한 Zotero (리눅스 머신)
* Python 3과 잡다 패키지들
* 네트워크 위치인 ZotSyncFolder에 접근 가능한 아이패드
* Node.js
  * npm install zotero
  * npm install configparser

## 워크플로우
* 리눅스 머신에서 construct_folder.py를 실행하면 리눅스의 Zotero 폴더(~/Zotero)에서
  ZotSyncFolder의 폴더로 전체 pdf를 복사하고, json형태로 db 비슷한 것을 만든다.
* node zotero_notifier.js 로 PC측 갱신 알리미를 켜 둔다.
  * Zotero에 새로운 논문 넣으면 소켓으로 데이터 받아서, ZotSyncFolder를 동작시킨다.
* 마지막으로 동기화 프로그램인 file_watcher.py를 틀어 둔다.
  * 소켓에서 데이터 오면, 새로운 논문을 ZotSyncFolder에 저장시킨다.
  * 아이패드에서 ZotSyncFolder에 있는 논문을 열심히 보고 메모한다.
  * 아이패드에서 그 파일을 저장한다 (보통 노트 앱들 자동 저장함)
  * 1분에 한번씩 검사해서 새로운 파일을 Zotero에 업로드한다.
  
## Docker 쓰기
* 초기 실행 (또는 다 갈아 엎고 싶을 때)
  * 한번 실행 후 종료된다
  * docker run \
  --rm \
  --name zotsyncfolder_construct \
  --volume /media/kdm/kasumi_sshfs/97_webdav:/mount \
  kim135797531/zotsyncfolder_construct
* 갱신 감시기
  * docker run \
  --rm \
  --name zotsyncfolder_watcher \
  --volume /media/kdm/kasumi_sshfs/97_webdav:/mount \
  kim135797531/zotsyncfolder_watcher
* 갱신 알리미 (Node.js)  
  * docker run \
  --rm \
  --name zotsyncfolder_notifier \
  --volume /media/kdm/kasumi_sshfs/97_webdav:/mount \
  kim135797531/zotsyncfolder_notifier
  
## 현재 가능한 것

* 첫 초기화
  * ZotSyncFolder 구조를 만들고 Zotero 모든 파일 일괄 다운로드
  * 동기화할 파일 확장자 선택 가능
* Zotero -> ZotSyncFolder
  * Zotero에 신규 항목이 들어갔을 때, ZotSyncFolder에 해당 항목 추가
  * Zotero의 첨부 파일이 변경되었을 때, ZotSyncFolder의 해당 파일 업데이트
* ZotSyncFolder -> Zotero
  * ZotSyncFolder의 첨부 파일이 변경되었을 때, Zotero에 이를 알리고 해당 파일 업데이트

## 현재 못 하는 것 (하면 난리남)

현재로서는 아래 작업들을 하려면 그냥 ZotSyncFolder 싹 지운 다음에 다시 초기화해야됨
 
* Zotero -> ZotSyncFolder
  * 새로운 컬렉션 생성, 수정 (절대 시도도 하지 마라)
  * 아이템의 컬렉션 간 이동 (절대 시도도 하지 마라)
  * 아이템 삭제 (ZotSyncFolder에는 계속 남아있음)
  * 이상한 이름을 가진 pdf 파일 전송 (파일 이름 수정 안 함)
* ZotSyncFodler -> Zotero
  * 아이패드에서 새로운 아이템 추가

## 기타 메모
* 용어 접두사 설명 1
  * original = Zotero 로컬 저장소
  * server = WebDAV 저장소
  * new = zotsyncfolder 저장소
* 용어 접두사 설명 2
  * collection = Zotero 컬렉션
  * item = Zotero 아이템, 또는 (컬렉션, 아이템, 첨부파일) 중에 하나
  * attachment = Zotero 첨부파일
  * 함수 위치에 따라 암묵적으로 original, server, new 안 붙인 것들이 섞여 있음 ㅅㅂㅋㅋ
* 자료형 설명
  * collection, item, attachment는 다 json -> dict
    * zotero에서 내려준 풀 dict
    * zotsyncfolder에서 쓰려고 만든 간단한 dict
    * 이거도 섞여 있으니 잘 디버깅 ㄱ
   