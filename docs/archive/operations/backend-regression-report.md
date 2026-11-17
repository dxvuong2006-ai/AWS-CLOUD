# [Lịch sử] Báo cáo kiểm thử hồi quy Backend - LearnCloud

> **TÀI LIỆU LỊCH SỬ - KHÔNG PHẢI KẾT QUẢ MỚI NHẤT.** Thời điểm áp dụng: lượt regression được lưu trước đợt tài liệu ngày 17/11/2026. Kết quả 463 pass/69 skip không được chạy lại trong lần dọn tài liệu này; xem [tài liệu kiểm thử hiện tại](../../04-evaluation/testing.md) để phân biệt các lượt đo.

## Kết quả thực tế

| Lượt chạy | PASS | FAIL | SKIP | ERROR | Ghi chú |
|---|---:|---:|---:|---:|---|
| Ban đầu | 440 | 22 | 69 | 0 | 531 test được collect; 9 unittest subtests pass |
| Sau cập nhật trước đó | 463 | 0 | 69 | 0 | 532 test được collect; 9 unittest subtests pass |
| Chạy lại trong lượt này | **463** | **0** | **69** | **0** | 532 test; 9 unittest subtests pass; 161 warnings; 85,46 giây |

Lượt cuối: `python -m pytest tests -q -rs -p no:cacheprovider` từ `backend/`, với `DATABASE_URL=sqlite:///:memory:`, credential AWS giả, AWS profile được gỡ khỏi tiến trình, và các PostgreSQL opt-in gate tắt. Không truy cập AWS/RDS; không dùng `DATABASE_URL` làm test DB PostgreSQL. Cache pytest tắt do workspace cache không có quyền ghi.

Một lượt chạy chẩn đoán trước đó có 30 lỗi `botocore.exceptions.ProfileNotFound` vì shell kế thừa `AWS_PROFILE=learncloud` trong khi không có profile file. Bỏ profile rồi chạy lại thì đạt kết quả trên. Đây là lỗi cấu hình môi trường của lượt chẩn đoán, không phải regression ứng dụng/test. Không đổi test để biến các lỗi này thành skip.

## 69 test skip: nguyên nhân và cấu hình theo nhóm

### Guard truy cập, tiến độ và luồng quiz — 5

- `test_access_guards_postgres.py` (1): `test_postgres_guards_enrollment_publish_unlock_and_ownership`.
- `test_progress_postgres.py` (2): `test_progress_schema_is_available_in_isolated_postgres`, `test_progress_postgres_idempotency_resume_and_concurrent_sequence`.
- `test_quiz_flow.py` (2): `test_postgres_checkpoint_flow_and_idempotent_concurrent_submit`, `test_postgres_unapproved_previous_checkpoint_blocks_bypass`.

**Nguyên nhân/gate:** không đặt `LEARNCLOUD_TEST_DATABASE_URL`, hoặc URL dùng port 15437 (bị chặn để tránh local RDS tunnel). Cần URL riêng tới loopback PostgreSQL test DB có schema đã migrate, dùng `postgresql://<test-user>:<test-password>@127.0.0.1:<port-khac-15437>/<test-db>`. Không dùng `DATABASE_URL`.

### Cấp tài khoản Cognito trên PostgreSQL — 7

`test_cognito_provisioning_pg.py`: `test_pg_first_login_provisions_once`, `test_pg_verify_retry_repairs_confirmed_identity`, `test_pg_email_conflict_does_not_rebind`, `test_pg_subject_and_email_cross_conflict_changes_neither_row`, hai ca tham số hóa của `test_pg_unprovisionable_cognito_state_creates_no_row`, và `test_pg_concurrent_first_login_is_idempotent`.

**Nguyên nhân/gate:** thiếu `LEARNCLOUD_RUN_AUTH_DB_TESTS=1` và URL riêng. `LEARNCLOUD_AUTH_TEST_DATABASE_URL` phải trỏ loopback DB/user `learncloud_auth_test`, có schema migration `0007`. Guard từ chối DB/user/host/query không đúng. Cognito được mock, không gọi AWS.

### Đối soát migration 0010 — 14

`test_migration_0010_consistency.py`: 6 ca `test_reconciles_historical_0004_states_and_preserves_registry`, cùng `test_repeat_is_idempotent_and_preserves_data`, `test_historical_runner_reproduces_0004_collision_and_0005_block`, `test_canonical_chain_plus_0010_has_current_backend_prerequisites`, `test_failure_rolls_back_all_changes`, và 4 ca tham số hóa `test_guard_refuses_non_isolated_targets`.

**Nguyên nhân/gate:** thiếu `LEARNCLOUD_RUN_P06_DB_TESTS=1` và `LEARNCLOUD_P06_TEST_DATABASE_URL`. URL guard yêu cầu loopback, port **55432**, database/user **learncloud_p06_test**, không có query ngoài `connect_timeout` và `application_name`. Test reset schema `public`, nên DB phải chuyên dụng và user test có quyền phù hợp. Fixture tự chạy schema/migration cần thiết.

### Migration 0014 và 0015 — 2

- `test_progress_trigger_permissions_postgres.py`: `test_0014_runtime_duration_update_syncs_progress_without_direct_progress_privileges`.
- `test_migration_0015_user_account_status.py`: `test_0015_adds_active_status_preserves_accounts_and_grants_only_runtime_status_access`.

**Nguyên nhân/gate:** cần `LEARNCLOUD_RUN_0014_PG_TESTS=1` + `LEARNCLOUD_0014_TEST_DATABASE_URL` và `LEARNCLOUD_RUN_0015_PG_TESTS=1` + `LEARNCLOUD_0015_TEST_DATABASE_URL`. PostgreSQL 16 loopback, tách DB/user/port: `learncloud_0014_test` trên **55434**, `learncloud_0015_test` trên **55435**. Test 0015 yêu cầu login test superuser và xác nhận các role runtime chưa tồn tại trước khi chạy migration.

### Migration hoàn thành tiến độ và phiên Tutor — 2

- `test_progress_completion_postgres.py`: `test_backfilled_duration_reconciles_and_tracks_persisted_progress_on_postgresql`.
- `test_tutor_session_postgres.py`: `test_tutor_session_migration_and_orm_query_on_postgresql`.

**Nguyên nhân/gate:** thiếu `LEARNCLOUD_RUN_TUTOR_PG_TESTS=1` và `LEARNCLOUD_P06_TEST_DATABASE_URL`; cần PostgreSQL 16 loopback DB/user `learncloud_p06_test` port **55432**. Mỗi test tạo schema UUID riêng và dọn schema đó.

### Lưu bản nháp review — 1

`test_review_draft_postgres.py`: `test_review_save_commit_reload_and_partial_patch_on_postgresql`.

**Nguyên nhân/gate:** thiếu `LEARNCLOUD_REVIEW_TEST_DATABASE_URL`. URL phải là loopback port **15438**, DB/user `learncloud_review_test`, không query parameter. Test tạo bảng từ ORM metadata.

### Xác nhận upload — 3

`test_upload_confirmation_pg.py`: `test_concurrent_requests_reserve_one_immutable_key`, `test_confirmation_persists_exact_raw_and_blocks_fresh_upload`, `test_legacy_raw_recovery_cli_is_preview_first_and_one_time`.

**Nguyên nhân/gate:** thiếu `LEARNCLOUD_RUN_UPLOAD_DB_TESTS=1` và `LEARNCLOUD_UPLOAD_TEST_DATABASE_URL`. URL phải tới loopback DB/user `learncloud_auth_test`; cần có bảng `public.video_uploads`. S3 được thay bằng doubles.

### AI worker và ledger pipeline video — 10

- `test_ai_worker_db.py` (2): `test_k5_transaction_and_retry_idempotency_on_postgresql`, `test_concurrent_k5_generate_creates_one_material_set_on_postgresql`.
- `test_video_pipeline_ledger_db.py` (8): `test_0004_and_reviewed_0005_constraints_are_present_and_validated`, `test_database_rejects_cross_lesson_upload_reference`, `test_two_uploads_same_lesson_only_one_can_claim_generation_zero`, `test_uploaded_lesson_with_valid_ledger_and_no_runs_claims_generation_zero`, `test_real_course_lock_rejects_concurrent_claim_before_s3_or_second_run`, `test_database_unique_constraint_rejects_same_upload_attempt`, `test_complete_job_persists_output_duration_and_processed_key`, `test_old_callback_cannot_replace_new_attempt_processed_key`.

**Nguyên nhân/gate:** thiếu `LEARNCLOUD_RUN_PIPELINE_DB_TESTS=1` và `LEARNCLOUD_PIPELINE_TEST_DATABASE_URL`; URL loopback DB `learncloud_pipeline_test`. DB phải có migrations `0004` và reviewed `0005`, cùng 2 Lesson/Course DRAFT sạch được operator chuẩn bị. Ledger test không tự migrate/tạo fixture nghiệp vụ và rollback DML. AWS client/API bị cấm.

### API xử lý video với PostgreSQL — 10

`test_video_processing_db.py`: `test_status_reads_actual_postgres_and_redacts_error`, `test_retry_transaction_and_duplicate_request`, `test_dispatch_failure_rolls_back_real_postgres_update`, `test_unconfigured_workflow_keeps_real_failure_state`, `test_non_failed_real_lesson_cannot_retry`, `test_course_lock_blocks_concurrent_retry_and_publish_without_waiting`, `test_lesson_lock_blocks_concurrent_retry_without_dispatch`, `test_publish_real_existing_course_is_idempotent`, `test_draft_course_with_legacy_published_lessons_has_no_approval_proof`, `test_approve_then_publish_after_operator_applies_migration`.

**Nguyên nhân/gate và giới hạn:** skip nếu `LEARNCLOUD_RUN_DB_TESTS != 1`. Lớp unittest lấy `engine` đã tạo từ `app.database`, tức phụ thuộc `settings.DATABASE_URL`; không có URL test riêng. Theo yêu cầu không dùng application `DATABASE_URL` làm test DB, không bật gate bằng cách gán PostgreSQL URL vào biến này. Cần tách cấu hình test engine trước khi chạy nhóm này. Không sửa test trong lượt này vì chưa có phương án harness được kiểm chứng.

### Cấp tài khoản local auth cần PostgreSQL role thật — 15

`test_local_auth_provisioning.py`: 4 ca tham số hóa của `test_postgres_provisioning_preview_write_boundaries_and_existing_data`, 9 ca của `test_postgres_wrong_target_or_unsafe_input_never_enrolls`, `test_postgres_unapproved_login_and_set_role_are_rejected`, và `test_actual_cli_preview_confirmation_and_apply`.

**Nguyên nhân/gate:** `LEARNCLOUD_RUN_AUTH_DB_TESTS=1`; `LEARNCLOUD_AUTH_TEST_DATABASE_URL` theo guard loopback DB/user `learncloud_auth_test`. Cần quyền/ACL PostgreSQL thật và role `learncloud_auth_denied`; CLI chỉ chạy trên DB test cho phép. Các ca offline/mocked cùng module đã pass.

Tổng số: **5 + 7 + 14 + 2 + 2 + 1 + 3 + 10 + 10 + 15 = 69 skipped cases**. Đây là các gate PostgreSQL có chủ đích, không tính là pass; hành vi PostgreSQL chưa được xác minh.

## Trạng thái Docker PostgreSQL 16

Không thể dựng container hoặc chạy 69 PostgreSQL test trong lượt này. Docker CLI có mặt nhưng daemon không chạy: kiểm tra trong và ngoài sandbox đều báo named pipe `dockerDesktopLinuxEngine` không tồn tại; Docker Desktop executable/service/process không có trên máy. Vì vậy không thể đọc inventory container, kiểm tra image local, pull image, tạo container hoặc chạy gates. Không container/volume nào được sửa/xóa.

Compose dự án khai báo `learncloud-db`, volume `learncloud_data` và port 5434; **không dùng compose này làm test DB**. Môi trường test cần PostgreSQL 16 riêng bind loopback, credentials/DB test, và endpoints theo guard: port **55432**, **55434**, **55435**, **15438**; nhóm access/progress/quiz dùng port loopback riêng không phải 15437. Các DB auth/pipeline cần schema/migration/fixtures ghi ở trên. Không truyền URL production/RDS hay application `DATABASE_URL`. Việc dựng môi trường chưa thực hiện được do thiếu daemon.

## Việc còn lại

- 463 test offline/non-gated pass; 69 PostgreSQL cases vẫn skip và chưa chạy trên PostgreSQL 16.
- Cần cài/khởi động Docker Desktop hoặc cung cấp Docker daemon cục bộ; sau đó tạo DB/role/endpoints test chuyên biệt theo URL guard rồi bật gates.
- `test_video_processing_db.py` cần test engine tách khỏi application `DATABASE_URL`; giữ nguyên gate cho tới khi có cách an toàn.
- 161 warnings chủ yếu là deprecation FastAPI `on_event`, HTTPX shortcut và event loop của Mangum; không làm test fail.

## Thay đổi và phạm vi

Trong lượt này chỉ cập nhật báo cáo này. Không sửa fixture/test, mã ứng dụng, cấu hình Docker hay dữ liệu; không tạo/xóa/sửa container; không chạy migration trên DB thật; không deploy, commit hoặc push. Hai test file (`test_auth_integration.py`, `test_lesson_approval.py`) được nêu trong báo cáo trước là thay đổi từ lượt trước, không sửa trong lượt này.
