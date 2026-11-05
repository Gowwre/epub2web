# Nhật ký thay đổi

Mọi thay đổi đáng chú ý dành cho người dùng được ghi lại ở đây. Định dạng theo
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), và phiên bản theo
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Đây là bản dịch tiếng Việt của [`CHANGELOG.md`](CHANGELOG.md). Bản tiếng Anh là
nguồn chính thức cho GitHub Releases. Khi một phiên bản chưa có bản dịch, trang
web sẽ hiển thị ghi chú tiếng Anh của phiên bản đó.

## Chưa phát hành

## 0.13.1 - 2026-11-05

### Sửa lỗi

- Sửa lỗi **Kiểm tra cập nhật** trên bản AppImage Linux và bản macOS khi đường dẫn chứng chỉ OpenSSL từ máy dựng không tồn tại trên máy người dùng. Việc kiểm tra cập nhật giờ dùng bộ chứng chỉ Mozilla CA đi kèm.

## 0.13.0 - 2026-11-04

### Thêm mới

- Thêm nút chuyển giao diện Anh/Việt vào thanh điều hướng và **Cài đặt đọc**. Điều hướng, tìm kiếm, các nút đọc, đánh dấu và ghi chú, hộp thoại, nhãn trợ năng, thời gian đọc và tiêu đề tab trình duyệt có thể hiển thị bằng tiếng Việt. Văn bản và metadata của sách vẫn giữ nguyên ngôn ngữ gốc.
- Đóng gói bộ ký tự tiếng Việt cho Fraunces, Inter và Literata để nhãn giao diện tiếng Việt và sách tiếng Việt hiển thị đúng với phông chữ tự lưu trữ như các ngôn ngữ khác.
- Thêm giao diện tiếng Việt cho trang giới thiệu, trang tải xuống và nhật ký thay đổi, với nút chuyển ngôn ngữ trên thanh điều hướng và thẻ `hreflang` cho từng trang.
- Dịch ghi chú phát hành sang tiếng Việt trong `CHANGELOG.vi.md`. Trang nhật ký thay đổi dùng bản dịch khi phiên bản và ngày khớp với changelog gốc, và tự động quay về ghi chú tiếng Anh khi bản dịch chưa có.
- Thêm nút chuyển giao diện Anh/Việt vào ứng dụng desktop. Nút trên thanh đầu trang đổi giao diện ngay và ghi nhớ lựa chọn; trạng thái, lỗi, nhãn tiến trình, hộp chọn tệp và hộp thoại cập nhật đều được dịch. Nhật ký dựng và ghi chú phát hành trên GitHub vẫn bằng tiếng Anh.

### Thay đổi

- Tự nhận diện ngôn ngữ hệ thống hoặc trình duyệt trong lần truy cập đầu. Trang giới thiệu đưa khách dùng tiếng Việt sang bản tiếng Việt, trình đọc được tạo sẽ mở bằng tiếng Việt khi tiếng Việt là ngôn ngữ hệ thống ưu tiên, và ứng dụng desktop theo ngôn ngữ hệ thống trong lần khởi động đầu. Mọi ngôn ngữ khác dùng tiếng Anh, và lựa chọn ngôn ngữ thủ công vẫn được ghi nhớ.

## 0.12.0 - 2026-11-04

### Thêm mới

- Đánh dấu đoạn văn và thêm ghi chú tùy chọn trong khi đọc. Chọn văn bản để đánh dấu chỉ với một thao tác, nhấp vào một dấu để sửa ghi chú hoặc màu, và mở **Đánh dấu & ghi chú** trên thanh đầu trang để xem lại theo chương, quay lại đoạn văn hoặc xóa bằng Hoàn tác.
- Xuất và nhập đánh dấu dưới dạng JSON từ bảng **Đánh dấu & ghi chú**. Đánh dấu và ghi chú ở lại trong trình duyệt và không bao giờ được ghi vào trang đã tạo.
- Xuất đánh dấu và ghi chú dưới dạng Markdown dễ đọc, hoặc sao chép tất cả chỉ với một thao tác để đưa sang ứng dụng ghi chú hay tài liệu. JSON vẫn là định dạng sao lưu.
- Tìm kiếm đánh dấu và ghi chú cục bộ theo trích dẫn, ghi chú hoặc tên chương. Tìm kiếm kết hợp với các bộ lọc Tất cả, Đánh dấu và Ghi chú, và không bao giờ được thêm vào chỉ mục tìm kiếm đã xuất bản.
- Giúp phím tắt dễ khám phá hơn: nút **Phím tắt** và phím `?` mở hộp thoại tham khảo, nút tìm kiếm hiển thị `/`, thanh công cụ khi chọn văn bản hiển thị `H` và `N`, và khung soạn ghi chú hiển thị phím tắt lưu. Menu và chân trang cũng liên kết đến phần tham khảo này.

### Thay đổi

- Giải thích rằng đánh dấu và ghi chú ở lại trong trình duyệt, và chỉ yêu cầu lưu trữ lâu dài sau khi người dùng chọn **Giữ trên thiết bị này**. Trình duyệt không bao giờ bị hỏi quyền lưu trữ tự động.
- Tinh chỉnh trang giới thiệu với thiết kế sạch hơn, đặt sản phẩm lên trước: ảnh chụp trình đọc thật, bảng thông tin bản dựng, lưới tính năng kiểu bento và cấu trúc trang đơn giản hơn trên máy tính lẫn điện thoại. Ảnh mạng xã hội cũng được làm lại cho khớp.
- Chuyển epub2web sang giấy phép GPL-3.0-or-later. EPUB và văn bản sách vẫn thuộc về bạn; trang đã tạo có chứa giao diện đọc theo GPL, nên hãy giữ thông báo giấy phép khi phân phối lại. Phân phối phiên bản epub2web đã sửa đổi giờ đây yêu cầu công khai mã nguồn theo cùng giấy phép.

### Sửa lỗi

- Lưu nhật ký CLI trong thư mục dữ liệu ứng dụng của hệ điều hành, khớp với ứng dụng desktop và vị trí được ghi trong tài liệu.

## 0.11.0 - 2026-11-03

### Thêm mới

- Thêm nút **Kiểm tra cập nhật** trên thanh đầu trang của ứng dụng desktop, báo khi ứng dụng đã là bản mới nhất hoặc khi kiểm tra thất bại.

### Thay đổi

- Kiểm tra GitHub Releases khoảng một lần mỗi giờ khi ứng dụng desktop đang mở, thay vì chỉ kiểm tra lúc khởi động.

## 0.10.0 - 2026-11-02

### Thêm mới

- Kéo tệp EPUB vào ứng dụng desktop để chọn. Thẻ nguồn được tô sáng khi tệp nằm trên đó, và các tệp không được hỗ trợ sẽ được báo mà không làm gián đoạn lựa chọn hiện tại.

## 0.9.0 - 2026-10-30

### Thêm mới

- Hiển thị phiên bản ứng dụng bên cạnh tên sản phẩm và trong tiêu đề cửa sổ của ứng dụng desktop.

## 0.8.0 - 2026-10-30

### Thay đổi

- Dựng trang mục lục và điều hướng chương từ cây mục lục của EPUB, bao gồm các phần và mục lồng nhau. Các trang trong spine không có trong mục lục, như phần tóm tắt tài liệu do máy tạo, không còn xuất hiện như chương.

### Sửa lỗi

- Tách một tài liệu trong spine thành các trang đọc riêng tại các neo mục lục của EPUB, để các chương dùng chung một tệp HTML xuất hiện riêng trong mục lục và điều hướng chương.
- Đọc các mục NCX lồng nhau dưới dạng cây thay vì làm phẳng, và giải mã các đoạn mục lục được mã hóa phần trăm.
- Xem phần mở đầu (prologue) là phần đầu sách và bắt đầu đọc từ đó khi sách có phần này.

## 0.7.0 - 2026-10-30

### Thêm mới

- Thêm hộp thoại lần mở đầu tiên trên trang tải xuống, mở khi quá trình tải bắt đầu và hiển thị các bước cài đặt cho nền tảng đã chọn.

### Thay đổi

- Viết lại trang giới thiệu, trang tải xuống và phần mở đầu README bằng giọng văn giản dị hơn, tập trung vào tác giả, người dịch và nhà xuất bản nhỏ.
- Dùng logo chim cánh cụt Linux cho thẻ tải Linux trên trang giới thiệu thay vì biểu tượng terminal.

### Sửa lỗi

- Sửa lỗi ứng dụng desktop bị treo ở “Starting preview…” mà không mở trình duyệt, đặc biệt trên bản macOS, bằng cách gửi URL xem trước dưới dạng sự kiện có cấu trúc và đẩy ngay biểu ngữ máy chủ.

## 0.6.0 - 2026-10-29

### Thêm mới

- Thêm cài đặt đọc cho cỡ chữ và giãn dòng, được ghi nhớ cục bộ trong trình duyệt.
- Thêm kiểu đoạn văn, độ rộng trang và các tùy chọn giao diện Tự động/Sáng/Tối vào cài đặt đọc. Giao diện Tự động theo thiết bị cho đến khi người dùng chọn giao diện thủ công.
- Thêm lối tắt **Đọc** gọn trên thanh đầu trang điện thoại để hành động đọc ở trang chủ luôn sẵn dùng mà không cần cuộn.
- Làm bảng mục lục trên điện thoại gọn hơn bằng cách thu gọn các mục của chương khi cần, tô sáng chương hiện tại và mở đúng vị trí chương đó.
- Thêm điều hướng bằng phím mũi tên và Enter cho kết quả tìm kiếm.
- Duyệt hình trong trình xem ảnh bằng nút trước/sau, bộ đếm hình và điều hướng bằng phím mũi tên.
- Thêm thanh nhảy A–Z vào chỉ mục, liên kết đến mục đầu tiên của mỗi chữ cái và bỏ qua mạo từ cũng như dấu ngoặc kép ở đầu.
- Thêm bộ ký tự phông chữ tự lưu trữ cho tiếng Hy Lạp, Kirin, Ả Rập, Do Thái, Devanagari, Thái và CJK, chỉ sao chép các hệ chữ có trong sách vào trang tương ứng.
- Thêm hỗ trợ bố cục phải sang trái cho các ngôn ngữ sách RTL, gồm định vị logic và mũi tên điều hướng được lật.
- Đếm độ dài đọc của CJK và tiếng Thái theo ký tự cho ước tính và tiến trình toàn sách.

### Thay đổi

- Tăng nhẹ cỡ chữ mặc định trên điện thoại, làm liên kết mục trong thanh bên dễ chạm hơn và giữ chương đang đọc hiển thị trong mục lục dài.
- Phím mũi tên chuyển trang giờ bỏ qua vùng chọn văn bản, phím bổ trợ, bảng và khối mã để không làm gián đoạn cuộn ngang.
- Dùng chính tiêu đề trong EPUB cho tiêu đề phần đầu và phần cuối sách, tránh dòng tiêu đề trùng lặp bên dưới tiêu đề trang.
- Bố trí đúng cho mục chỉ mục và danh sách tham khảo: mục chỉ mục lồng nhau, thụt lề treo cho trích dẫn và chỉ mục hai cột trên màn hình rộng.

### Sửa lỗi

- Khôi phục chữ cái đầu chương dạng hình ảnh thành vật trang trí nổi hòa với nền giấy thay vì bị thu nhỏ thành một dấu nội tuyến tí hon.
- Ngăn tiêu đề chương và URL dài tràn ra ngoài mép trang, đặc biệt trên điện thoại.
- Làm tham chiếu hình như “Hình 1.2” nhảy đến đúng hình thay vì cuộn qua chú thích.
- Không lặp lại tiêu đề chương hai lần trong thẻ chương trước/sau.
- Tự động đưa con trỏ vào ô tìm kiếm và cải thiện tên trợ năng của logo trên thanh đầu trang.

## 0.5.0 - 2026-10-29

### Thêm mới

- Thêm hành động **Thay đổi…** bên cạnh đường dẫn đầu ra của ứng dụng desktop để bạn chọn nơi lưu trang đã tạo. Ứng dụng tạo thư mục `<book>-site` bên trong vị trí đã chọn.
- Ghi nhớ vị trí đọc và hiển thị tiến trình toàn sách, với hành động **Đọc tiếp** trên trang chủ và tùy chọn **Đọc lại từ đầu**. Vị trí được lưu cục bộ trong trình duyệt theo từng tệp EPUB; dựng lại cùng một EPUB sẽ giữ nguyên vị trí, còn EPUB khác sẽ bắt đầu vị trí riêng.

### Thay đổi

- Dùng cổng xem trước cục bộ ổn định trong ứng dụng desktop để trình duyệt giữ được vị trí đọc giữa các lần chạy.

### Sửa lỗi

- Hiển thị đúng các đường dẫn nằm trực tiếp trong thư mục home của ứng dụng desktop thay vì thêm tiền tố `~.` thừa.

## 0.4.0 - 2026-10-29

### Thêm mới

- Thêm lối tắt GitHub và trang web dự án vào thanh đầu trang của ứng dụng desktop.
- Kiểm tra GitHub Releases khi khởi động ứng dụng desktop và hiển thị nút **Cập nhật** khi có phiên bản mới hơn. Nút này mở ghi chú phát hành và liên kết đến trang tải xuống. Việc kiểm tra chạy trong nền, im lặng khi ngoại tuyến và có thể tắt bằng `EPUB2WEB_NO_UPDATE_CHECK=1`.

### Thay đổi

- Trỏ nút Ghi chú phát hành trên trang tải xuống đến nhật ký thay đổi của trang thay vì trang phát hành GitHub.

## 0.3.0 - 2026-10-28

### Thêm mới

- Thêm trang giới thiệu Astro công khai và trang tải xuống, kèm FAQ lần mở đầu tiên cho cảnh báo Windows SmartScreen và macOS Gatekeeper. Quy trình Pages xuất bản trang giới thiệu tại gốc dự án và chuyển bản demo trực tiếp sang `/demo/`.
- Thêm trang nhật ký thay đổi riêng với liên kết GitHub cho mỗi bản phát hành đã công bố.
- Thêm hướng dẫn “Chạy trang web” vào README và trang giới thiệu, bao gồm xem trước trên desktop, mở lại trang, lệnh máy chủ tĩnh cục bộ và lý do không thể mở trực tiếp `index.html`.
- Đánh dấu trang đã tạo bằng tệp `.epub2web` và thẻ meta generator để việc làm mới không thể ghi đè nhầm thư mục không liên quan.

### Thay đổi

- Nút tải xuống giờ trỏ trực tiếp đến tệp Windows, macOS và Linux của bản phát hành hiện tại thay vì trang phát hành GitHub. Bản dựng Pages tự tìm tài nguyên mới nhất, và một bản phát hành mới sẽ làm mới trang tải xuống tự động.
- Nhận diện nền tảng của khách truy cập trên trang tải xuống, đề xuất và tô sáng bộ cài phù hợp, đồng thời quay về bộ chọn nền tảng trung lập trên điện thoại, ChromeOS, Linux ARM, tác nhân lạ hoặc khi không có JavaScript.
- Xóa các tài nguyên giao diện xem trước ghi chú và lọc chỉ mục không còn hoạt động khỏi giao diện đọc.

### Sửa lỗi

- Ngăn bố cục di động hẹp cắt mất phần đầu trang chủ, thanh đầu trang, kết quả đầu ra bản phát hành và các đoạn mã dài.
- Hiển thị thời gian đọc ước tính của mỗi trang thay vì dòng chapter-meta trống.
- Từ chối các liên kết nội bộ có đoạn `..` thoát khỏi trang đã tạo, và yêu cầu liên kết gốc tuyệt đối phải chứa base path đã cấu hình.
- Giữ nguyên các ID nguồn EPUB hợp lệ trước đây bị trùng với ID mẫu như `main` hoặc `top`.
- Tách tiêu đề ghi đè có dấu hai chấm hoặc gạch ngang một cách nhất quán, và đọc năm từ ngày xuất bản không theo ISO thay vì hiển thị tháng bị cắt cụt.
- Giữ lại ZIP hỗ trợ khi một dòng sự kiện JSONL bị hỏng.
- Phân giải đường dẫn nhật ký và báo cáo tương đối của GUI theo thư mục làm việc của worker.

### Bảo mật

- Tăng cường làm sạch SVG bên ngoài bằng cách xóa các phần tử hoạt ảnh SMIL và giá trị thuộc tính `javascript:`, `file:` và `data:`.

### Lưu ý nâng cấp

- Các trang được tạo trước bản phát hành này không có dấu `.epub2web`. Làm mới một trang như vậy mà không dùng `--force` sẽ bị từ chối; hãy truyền `--force` một lần để chuyển đổi và thêm dấu.

## 0.2.0 - 2026-10-28

### Thêm mới

- Thêm GUI desktop Tkinter đa nền tảng (`epub2web-gui`) với bộ điều khiển worker độc lập với toolkit, điều khiển vòng đời xem trước và hỗ trợ chế độ worker của PyInstaller.
- Thêm báo cáo tiến trình theo từng hình, từng trang, bước dựng, bước kiểm tra và kiểm tra liên kết, với thanh tiến trình xác định trong GUI và các dòng nhật ký mốc quan trọng.
- Thêm `make gui-portable` và quy trình phát hành tạo các bản desktop độc lập: một tệp `.exe` cho Windows, một `.dmg` cho macOS và AppImage hoặc tarball di động cho Linux, kèm kiểm thử smoke đóng gói, checksum và thông báo giấy phép bên thứ ba.
- Thêm quy trình **Phát hành** chạy theo tag, kiểm tra `vX.Y.Z` với phiên bản gói, dựng các bản Python và bản di động, tạo bản phát hành GitHub và kích hoạt xuất bản PyPI.

### Thay đổi

- Chạy lại lệnh cho một trang epub2web đã có giờ sẽ làm mới trang đó tự động thay vì báo lỗi “output already exists”. Các thư mục không liên quan vẫn bị từ chối.
- Làm mới GUI desktop với bảng màu giấy của trình đọc, kiểu chữ tùy chỉnh, thẻ nguồn/đầu ra, chỉ báo trạng thái, tiêu đề nhận biết metadata, thanh cuộn bảng điều khiển bản dựng tùy chỉnh và biểu tượng ứng dụng.
- Tạo ghi chú phát hành GitHub từ phần `CHANGELOG.md` tương ứng thay vì ghi chú do GitHub suy ra từ commit.
- Công bố cảnh báo lần mở đầu tiên của Windows SmartScreen và macOS Gatekeeper, kèm cách xử lý riêng cho từng nền tảng, trong README và các gói di động.

### Sửa lỗi

- Giữ nguyên văn bản nguồn đã thoát trông giống markup, sửa các neo chú thích `#fnN`/`#ffnN` bị thiếu và chuẩn hóa các liên kết ngoài bị lỗi do chuyển đổi bản in.
- Báo cáo cả lỗi kiểm tra độ trung thực và liên kết nội bộ trong GUI desktop.

## 0.1.0 — 2026-10-26

- Bản phát hành công khai đầu tiên.
- Quy trình EPUB 2/3 → HTML ngữ nghĩa → trang tĩnh tất định.
- Cổng kiểm tra độ trung thực theo token và ký tự, cùng cổng kiểm tra liên kết nội bộ.
- Chỉ mục tìm kiếm tích hợp; không cần Node hay dịch vụ tìm kiếm bên ngoài.
- Giao diện sáng/tối, bố cục đọc thích ứng, mục lục, hình ảnh, ghi chú và hỗ trợ chỉ mục.
- Xem trước cục bộ chỉ với một lệnh bằng `--serve`.
- Hỗ trợ `--base-path` cho GitHub Pages và host dưới đường dẫn con.
- Đầu ra theo giai đoạn, ghi nguyên tử: bản dựng thất bại không làm thay đổi trang hiện có.
- Kiểm tra an toàn `--force` cho các đường dẫn đầu ra có thể ghi đè.
- Cổng đếm hình theo trang và cổng kiểm tra liên kết cho tài nguyên và tham chiếu ARIA.
- Báo lỗi rõ ràng khi hình bị thiếu, không hợp lệ hoặc ở xa; hỗ trợ hình dạng data-URI.
- Làm sạch markup EPUB không tin cậy và thoát metadata JSON-LD an toàn.
- Giữ nguyên điều hướng lồng nhau, vùng chứa cấu trúc, văn bản định dạng trước, danh sách định nghĩa và MathML.
- Chẩn đoán lần chạy bền vững: nhật ký dễ đọc, sự kiện JSONL, tài nguyên fidelity/link/summary và điều khiển `--log-dir`/`--log-file`.
- Giữ các neo mục lục cấp thân tài liệu kiểu Calibre và cải thiện nhận diện phần/phần đầu/phần cuối sách cho sách không có chương đánh số.
- ZIP hỗ trợ khi thất bại gồm README, nhật ký, sự kiện JSONL, bản tóm tắt và báo cáo kiểm tra; điều khiển `--report-dir`.
