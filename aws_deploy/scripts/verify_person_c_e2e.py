"""Kiểm tra luồng C trên môi trường demo đã chuẩn bị dữ liệu riêng.

Script ghi dữ liệu thật vào API được chỉ định. Chỉ dùng database demo;
tác vụ AI có thể phát sinh chi phí khi sử dụng dịch vụ thật.
"""
import argparse
import sys
import httpx


def main():
    """Chạy chuỗi kiểm tra với mã bài, chương và người dùng do người vận hành cấp."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    for name in ("lesson-id", "section-id", "next-section-id", "course-id"):
        parser.add_argument("--" + name, type=int, required=True)
    parser.add_argument("--student-id", type=int, default=1)
    parser.add_argument("--instructor-id", type=int, default=2)
    parser.add_argument("--transcript", required=True)
    args = parser.parse_args()
    instructor = {"X-Demo-User": str(args.instructor_id)}
    student = {"X-Demo-User": str(args.student_id)}
    with httpx.Client(base_url=args.base_url, timeout=180) as client:
        def call(method, path, **kwargs):
            response = client.request(method, path, **kwargs)
            response.raise_for_status()
            print("\033[32m[SUCCESS]\033[0m", method, path)
            return response.json()
        draft = call("POST", f"/lessons/{args.lesson_id}/review-drafts",
                     headers=instructor, json={"transcript": args.transcript,
                                               "allow_fallback": True})
        call("POST", f"/lessons/{args.lesson_id}/approve",
             headers=instructor, json={"expected_revision": draft["revision"]})
        call("POST", f"/courses/{args.course_id}/publish", headers=instructor)
        quiz = call("GET", f"/sections/{args.section_id}/quiz", headers=student)
        failed = call("POST", f"/quizzes/{quiz['id']}/attempts",
                      headers=student, json={"answers": []})
        if failed["passed"]:
            raise ValueError("Lượt thử đầu phải trượt.")
        wrong = next((r for r in failed["results"] if not r["is_correct"]), None)
        if not wrong or not wrong.get("options"):
            raise ValueError("Không tìm thấy câu sai hợp lệ.")
        # Nộp lại một lựa chọn sai để Tutor nhận lựa chọn thực sự đã lưu.
        wrong_choice = next((x for x in wrong["options"]
                             if x != wrong["correct_answer"]), None)
        failed = call("POST", f"/quizzes/{quiz['id']}/attempts",
                      headers=student, json={"answers": [
                          {"question_id": wrong["id"], "selected_answer": wrong_choice}]})
        call("POST", "/tutor/remediations", headers=student,
             json={"attempt_id": failed["id"], "lesson_id": args.lesson_id,
                   "question_id": wrong["id"], "selected_option": wrong_choice})
        answers = [{"question_id": row["id"], "selected_answer": row["correct_answer"]}
                   for row in failed["results"]]
        passed = call("POST", f"/quizzes/{quiz['id']}/attempts",
                      headers=student, json={"answers": answers})
        if not passed["passed"] or passed["score"] < 80:
            raise ValueError("Bài thi lại chưa đạt.")
        status = call("GET", f"/courses/{args.course_id}/unlock-status", headers=student)
        if not any(row["section_id"] == args.next_section_id and row["is_unlocked"]
                   for row in status):
            raise ValueError("Section tiếp theo chưa mở khóa.")
        print("\033[32m[SUCCESS] Luồng kiểm thử hoàn tất.\033[0m")


if __name__ == "__main__":
    try:
        main()
    except (httpx.HTTPError, ValueError, KeyError, StopIteration) as exc:
        print("[FAILED]", str(exc), file=sys.stderr)
        sys.exit(1)
