파일의 mtime(수정시각)으로 변경/삭제 감지

새/수정 파일만 ids 고정으로 add_documents() → 중복 방지

삭제된 파일의 청크는 ids로 제거

Chroma persist_directory에 저장 → 재시작 즉시 재사용

