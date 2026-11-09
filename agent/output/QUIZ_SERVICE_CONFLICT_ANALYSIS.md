# Phan tich xung dot quiz_service.py

Ngay: 2026-11-07

## 1. Muc tieu

Danh gia xung dot merge trong `backend/app/services/quiz_service.py` va de xuat
phien ban nen giu lai, tranh ghep hai luong quiz khac hop dong trong mot module.

## 2. Tai lieu va source da kiem tra

- `backend/app/services/quiz_service.py`
- `backend/app/api/quizzes.py`
- `backend/app/schemas/quiz.py`
- `backend/app/models/quiz.py`
- `backend/app/repositories/quizzes_repo.py`
- `backend/app/services/unlock_service.py`
- `backend/tests/unit/test_quiz_service.py`
- `backend/tests/unit/test_checkpoint_backend.py`
- `backend/tests/unit/test_learning_contract.py`
- `frontend/src/api/quizzes.api.js`
- `database/migrations/0004_checkpoint_attempt_idempotency.sql`

## 3. Hai ben xung dot

Worktree hien tai cua `quiz_service.py` co kich thuoc 0 byte va duoc danh dau
`UU`, nen file khong the import va chay duoc.

Stage 2 (HEAD/ours) la implementation luong quiz ban cu:

- `get_quiz_for_student`
- `get_unlocked_quiz_for_student`
- `submit_quiz`
- `get_student_quiz_history`
- DTO `QuizSubmitRequest`
- Khong co `request_id`, request fingerprint, idempotent replay
- Chi co flow co ban chua co checkpoint gate day du va remediation

Stage 3 (feature/theirs) la implementation checkpoint moi:

- `get_checkpoint`
- `submit_attempt`
- `attempt_history`
- Kiem tra enrollment, course publication, lesson progress, section unlock
- UUID `request_id` va fingerprint payload
- Replay cung request_id khi cung noidung
- HTTP 409 khi cung request_id duoc dung voi noi dung khac
- PDO row lock va attempt/answer/remediation atomic
- Luong low/medium/high score va can_retry/remediation_required
- Lich su va kich hoat AI remediation

## 4. By/chung hien tai nghieng ve phien ban nao

Phien ban feature/theirs phu hop hon voi frontend va database contract hien tai:

- Frontend checkpoint gui `request_id`, `lesson_id` va danh sach `answers`.
- Schema `QuizAttemptSubmitRequest` yeu cau UUID va cho phep omitted answer cho
  cau bo trong.
- Migration `0004_checkpoint_attempt_idempotency.sql` them `request_id`,
  `request_hash`, unique request key va bang checkpoint remediation.
- Model `QuizAttempt` va `CheckpointRemediation` da bo sung cac truong nay.
- Test checkpoint/backend biet get_checkpoint, submit_attempt, history,
  replay va remediation.
- Contract API mong muon kiem tra lesson, enrollment, publication va lock.

Stage HEAD/ours van co gia tri cho cac test legacy:

- `test_quiz_service.py` goi `submit_quiz` va `QuizSubmitRequest`.
- Repository lock va transaction cu co san cho submission.
- Service cu cung cap lich su va gan diem theo danh sach cau hoi.

Nhung day la hai API khac nhau, khong nen hop nhat bang cach giu ten cu va
anh xa ngam sang method moi.

## 5. De xuat xu ly

Nen resolve xung dot bang cach:

1. Giu implementation stage 3/feature lam phien ban quiz service chinh:
   - `get_checkpoint`
   - `submit_attempt`
   - `attempt_history`
2. Giu policy server goc:
   - PASS_SCORE = 80.
   - REMEDIATION_SCORE = 50.
   - Low score <50 bat buoc explanation, review va practice 66.67% tro len.
   - Medium score >=50 va <80 cho retry ngay.
   - Passed >=80.
3. Giu transaction va SQLite/PostgreSQL lock trong implementation moi.
4. Khong merge `QuizSubmitRequest` cu vao `QuizAttemptSubmitRequest` moi.
   Chon mot schema checkpoint duy nhat voi request_id bat buoc va selected_answer
   nullable.
5. Doi router `/sections/{section_id}/quiz` va
   `/quizzes/{quiz_id}/attempts` sang contract checkpoint/stateless result.
6. API history nen dung `attempt_history`, co paging, thay vi goi
   `get_student_quiz_history` cu neu endpoint dang duoc xac dinh la checkpoint history.
7. Neu can giu backward compatibility, tao aliases deprecated o lop thin adapter,
   khong giu hai implementation cham diem song song trong service:
   - `submit_quiz` chi delegate sang submit_attempt neu muon giu legacy caller.
   - `get_quiz_for_student` chi delegate sang get_checkpoint neu signature duoc
     mo rong va khong mat lesson_id.

Khong nen chon stage HEAD chi vi it thay doi. No se bi mat:

- Idempotency request_id.
- Fingerprint va replay.
- Remediation <50.
- Lesson/enrollment/course gates.
- Migration va DTO hien tai da them cho checkpoint.

Khong nen chi chon stage feature roi bo qua test cu ma khong co cac alias/router
compatibility co chu y, vi mot so module con import `submit_quiz`,
`QuizSubmitRequest`, `get_quiz_for_student`.

## 6. Pham vi files lien quan can resolve cung luc

Xung dot nay khong the sua rieng quiz_service:

- `backend/app/services/quiz_service.py`
- `backend/app/api/quizzes.py`
- `backend/app/schemas/quiz.py`
- Model/repository ho tro da co migration va thay doi.
- Test `test_quiz_service.py` va `test_checkpoint_backend.py`
- Frontend `quizzes.api.js`

Trong schema, ca hai nhom class van dang ton tai va xung dot marker da nam trong
file:

- Giữ `QuizAttemptSubmitRequest`, `QuizAttemptResultResponse`,
  `QuizAnswerResult`, `QuizDetailResponse` moi.
- Giữ hoac loai bo `QuizSubmitRequest` tuy theo backward compatibility.
- Khong de hai `QuizDetailResponse` definitions.

Trong router, endpoint POST va GET nen tra dung DTO moi va map HTTPException:

- 401 do auth.
- 403 cho enrollment, lesson progress, section lock, role, retry remediation.
- 404 cho quiz/section khong ton tai hoac chua approved.
- 422 cho duplicate question, unknown question, option khong hop le.
- 409 cho request_id da dung voi payload khac.

## 7. Trinh tu xu ly de an toan

1. Resolve `schemas/quiz.py` truoc.
2. Restore va resolve `services/quiz_service.py` theo contract checkpoint.
3. Resolve `api/quizzes.py` de thong nhat endpoint va DTO.
4. Resolve cac marker lien quan khac trong backend.
5. Chay test checkpoint va quiz service.
6. Neu test cu con import API cu, them compatibility wrapper hoac cap nhat test
   neu API cu da bi thay the co y thuc.
7. Chay OpenAPI test de xac nhan response code va schema.

Lenh kiem tra nho nhat sau khi co implementation:

- `python -m unittest tests/unit/test_checkpoint_backend.py -v`
- `pytest -q tests/unit/test_quiz_service.py tests/unit/test_learning_contract.py tests/unit/test_quiz_openapi.py`

## 8. Ket luan

Nghi loi xung dot cua quiz_service la viec chon giua hai phien ban khac chu de,
khong chi hai cach viet cung mot ham.

Nen uu tien checkpoint feature/theirs vi no phu hop migration, schema, frontend
va bo test moi. HEAD cu nen giu toi da trong vai alias compatible neu repository
van co code legacy goi den.
