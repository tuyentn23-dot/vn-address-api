# Bản 2.0.0 — triển khai và kiểm chứng trước khi bán

Đã kiểm tra local: 17 tests PASS, py_compile PASS. Chưa cập nhật hosting, chưa import account,
chưa publish, chưa có paid customer hoặc payout. Người dùng cho biết đã có RapidAPI/PayPal/hosting;
trạng thái đó chưa được kiểm chứng qua tài khoản.

Mã chính: src/main.py. Bộ tỉnh/thành hiện tại: data/provinces_2025.json (34 mã đối chiếu nguồn Chính phủ).
vn_provinces.json vẫn là snapshot lịch sử 63 tỉnh. src/legacy_v1_snapshot.py giữ mã trước nâng cấp
để phục hồi; không deploy snapshot đó làm phiên bản an toàn.
Phiên bản 2 thay đổi contract, bỏ bank lookup khỏi phạm vi bán và không suy luận nhân khẩu từ CCCD.
Không thay endpoint mà subscriber hiện có đang dùng trước khi kiểm tra và có kế hoạch version migration.

## Chạy và kiểm tra

Đặt RAPIDAPI_PROXY_SECRET bằng giao diện secret của hosting hoặc môi trường riêng, không đưa vào
chat, source, log, README hay shell command có giá trị thật. Thiếu secret thì business routes trả 503;
secret sai/thiếu trả 401. /health công khai chỉ trả trạng thái và phiên bản.

Chạy từ thư mục dự án: `uvicorn src.main:app --host 0.0.0.0 --port 8000 --no-access-log`.
render.yaml và Dockerfile hỗ trợ port của hosting. Không auto-deploy từ thay đổi local trong lượt này.
Free hosting có sleep/cold start không phải SLA paid; xác minh gói đang dùng trước khi bán.

Kiểm tra: `python -m unittest test_api.py -v`; `python build_listing.py`.
OpenAPI import candidate ở listing/openapi.import.json (3.0.3); URL placeholder phải được đổi
thành backend thật. Manifest và hash phải được cập nhật sau khi đổi URL. Không đổi phiên bản số
của spec 3.1 thành 3.0 mà không chuyển nullable/exclusive bounds; exporter đã xử lý các trường
dùng trong schema hiện tại. Chưa xác minh importer RapidAPI; vẫn cần thử private draft.

## Trình tự account

1. User đăng nhập RapidAPI seller hiện có trong tab Studio của ứng dụng.
2. Kiểm tra API đã tồn tại và subscriber để tránh duplicate hoặc breaking deployment.
3. Xác minh URL HTTPS ổn định và cách triển khai; cập nhật phiên bản dưới đường/version riêng nếu cần.
4. Backend health 200/version 2.0.0, request không được phép 401, request có proxy secret nhận kết quả đúng.
5. Chuẩn bị private draft/import OAS, đọc lại paths, base URL, README và security.
6. Đề xuất BASIC 0 USD/100 calls, PRO 9.99 USD/10,000 calls, ULTRA 29.99 USD/50,000 calls/tháng.
   Mọi plan hard limit, chưa overage; rate limits theo manifest. Batch tối đa 50 values vẫn là 1 request.
   Giá chỉ là thử nghiệm, chưa xác minh nhu cầu hoặc lợi nhuận; tính hosting/traffic/support trước khi lưu.
7. User xác nhận điều khoản/public listing khi cần; AGENTS.md yêu cầu explicit approval cho legal/financial actions.
8. Sau public, theo dõi free usage → paid subscriber → collected transaction → payout_received.
   Không ghi earned chỉ dựa trên subscribe; platform fee hiện 25%, payout PayPal có chu kỳ trễ.

Gói review: listing/README.md, listing/openapi.import.json, listing/manifest.json.
Không gửi outreach hoặc đăng nội dung marketing ngoài RapidAPI khi chưa được cho phép.
Không bật batch publisher để tạo hàng loạt sản phẩm trước một lần import/live gateway thành công.
