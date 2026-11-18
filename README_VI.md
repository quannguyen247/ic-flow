# Hướng Dẫn Chi Tiết Quy Trình Thiết Kế ASIC & FPGA Flow (Từ Cơ Bản Đến Nâng Cao)

Chào mừng bạn! Tài liệu này cung cấp cái nhìn tổng quan, dễ hiểu nhưng đầy đủ chuyên môn về **ASIC Flow** (Quy trình thiết kế vi mạch chuyên dụng) và **FPGA Flow** (Quy trình thiết kế phần cứng lập trình được).

Dù bạn là sinh viên, lập trình viên phần mềm muốn chuyển sang thiết kế phần cứng (IC Design), hay kỹ sư vi mạch mới bắt đầu, tài liệu này sẽ giải thích từng bước trong quy trình, so sánh sự khác biệt giữa ASIC & FPGA, và làm rõ các thuật ngữ cốt lõi một cách trực quan nhất.

## Chạy thử với bộ đếm 4 bit

Thư mục [example](example/README.md) đưa một bộ đếm 4 bit đi từ RTL đến GDSII. Mỗi giai đoạn nằm trong một thư mục đánh số và có sẵn file để chạy.

| Thư mục | Việc làm ở giai đoạn này |
| --- | --- |
| [`01_rtl`](example/01_rtl/README.md) | Viết đặc tả, code và mô phỏng bộ đếm thường |
| [`02_synthesis`](example/02_synthesis/README.md) | Dùng Yosys map RTL sang cell SKY130HD |
| [`03_dft`](example/03_dft/README.md) | Chèn scan bằng Fault, kiểm tra và chạy ATPG |
| [`04_physical`](example/04_physical/README.md) | Floorplan, placement, CTS và routing |
| [`05_gds`](example/05_gds/README.md) | Ghép DEF sau route với layout của cell thành file GDS |
| [`06_signoff`](example/06_signoff/README.md) | DRC KLayout và Magic, LVS KLayout và netgen, antenna, mô phỏng sau route, LEC, STA nhiều corner, đóng gói, [xem 3D](example/06_signoff/view3d/README.md) |

Chạy từng giai đoạn từ thư mục gốc của repo:

```sh
make -C example/01_rtl
make -C example/02_synthesis
make -C example/03_dft
make -C example/04_physical
make -C example/05_gds
make -C example/06_signoff
```

Mỗi thư mục có một link `build/` trỏ tới kết quả và log của nó. File GDSII là `example/05_gds/build/counter4.gds`, còn database của floorplan, placement, CTS và routing nằm trong `example/04_physical/build/`. Lệnh `make doctor` kiểm tra môi trường đã cài, `make all` chạy cả chuỗi và `make test` chạy test cho script điều khiển. Xem thêm [kết quả tham chiếu](example/REF_RESULT.md) để đối chiếu với máy của bạn.

RTL của bộ đếm chỉ có chức năng, chưa có scan. Fault chèn scan sau khi tổng hợp rồi cắt các flip-flop scan để chạy ATPG. OpenROAD nhận netlist scan vừa sinh ra, giữ nguyên flip-flop. Trước khi xuất layout, script so netlist đưa vào bước vật lý với đầu ra của DFT để chắc chắn hai bản giống nhau.

### Đọc kết quả kiểm tra cho đúng

Mô phỏng chỉ kiểm hành vi mà testbench chạm tới. Equivalence checking so hai bản mô tả mạch dưới các giả định đã nêu. STA kiểm các đường đã có ràng buộc và không cần vector thử. Mô phỏng gate-level chỉ có trễ khi bạn nạp dữ liệu trễ phù hợp, ví dụ SDF.

DRC chỉ kiểm các luật có trong bộ luật đã bật. LVS so mạch trích từ layout với bản tham chiếu. Kết quả đạt chỉ đúng với bộ luật, mô hình và bản tham chiếu đã dùng. Giới hạn của ví dụ này ghi trong [hướng dẫn signoff](example/06_signoff/README.md).

---

## Mục Lục
0. [Chạy thử với bộ đếm 4 bit](#chạy-thử-với-bộ-đếm-4-bit)
1. [So Sánh Tổng Quan: ASIC vs. FPGA](#1-so-sánh-tổng-quan-asic-vs-fpga)
2. [Quy Trình Thiết Kế ASIC Flow Chi Tiết](#2-quy-trình-thiết-kế-asic-flow-chi-tiết)
3. [Quy Trình Thiết Kế FPGA Flow Chi Tiết](#3-quy-trình-thiết-kế-fpga-flow-chi-tiết)
4. [Chuyên Sâu: Bản Chất Của LUT Trong FPGA (Look-Up Table, SRAM & LUTRAM)](#4-chuyên-sâu-bản-chất-của-lut-trong-fpga-look-up-table-sram--lutram)
   - [4.1. Bản chất thực sự của LUT là gì?](#41-bản-chất-thực-sự-của-lut-là-gì)
   - [4.2. Tại sao xét riêng LUT là Mạch Tổ Hợp, nhưng xét TOÀN MẠCH lại là Mạch Tuần Tự?](#42-tại-sao-xét-riêng-lut-là-mạch-tổ-hợp-nhưng-xét-toàn-mạch-lại-là-mạch-tuần-tự)
   - [4.3. Tại sao ô nhớ LUT phải là SRAM? (Bí mật giúp EDA Tool tái cấu trúc phần cứng)](#43-tại-sao-ô-nhớ-lut-phải-là-sram-bí-mật-giúp-eda-tool-tái-cấu-trúc-phần-cứng)
   - [4.4. Ngoại lệ: LUTRAM (Distributed RAM) là gì?](#44-ngoại-lệ-lutram-distributed-ram-là-gì)
5. [Giải Thích Các Thuật Ngữ Cốt Lõi (Glossary)](#5-giải-thích-các-thuật-ngữ-cốt-lõi-glossary)
   - [Pre-Synthesis vs. Post-Synthesis là gì?](#pre-synthesis-vs-post-synthesis-là-gì)
   - [Pre-Implementation vs. Post-Implementation là gì?](#pre-implementation-vs-post-implementation-là-gì)
   - [Linting & CDC là gì?](#linting--cdc-là-gì)
   - [TCL (Tool Command Language) là gì?](#tcl-tool-command-language-là-gì)
   - [DFT (Design for Testability) là gì?](#dft-design-for-testability-là-gì)
   - [STA (Static Timing Analysis) là gì?](#sta-static-timing-analysis-là-gì)
   - [Equivalence Checking / Formal Verification là gì?](#equivalence-checking--formal-verification-là-gì)
   - [Netlist, Standard Cells, GDSII & Bitstream là gì?](#netlist-standard-cells-gdsii--bitstream-là-gì)
6. [Sơ Đồ Tóm Tắt Luồng Thiết Kế](#6-sơ-đồ-tóm-tắt-luồng-thiết-kế)

---

## 1. So Sánh Tổng Quan: ASIC vs. FPGA

| Tiêu Chí | ASIC (Chip Chuyên Dụng Tùy Chỉnh) | FPGA (Chip Lập Trình Tái Cấu Trúc) |
| :--- | :--- | :--- |
| **Tên Đầy Đủ** | Application-Specific Integrated Circuit | Field-Programmable Gate Array |
| **Ẩn Dụ Dễ Hiểu** | **Nhà Đúc Bê Tông Kiên Cố**: Làm xong là cố định hoàn toàn, không thể sửa tường hay cửa sau khi đúc xong. | **Mô Hình Xếp Hình Lego**: Linh hoạt, tháo ra lắp lại cấu trúc mới bất kỳ lúc nào. |
| **Tính Linh Hoạt** | Cố định cứng sau khi sản xuất (không sửa được phần cứng). | Nạp lại file bitstream để thay đổi logic phần cứng chỉ trong vài giây. |
| **Chi Phí Ban Đầu (NRE)**| **Cực Kỳ Cao** (Từ $1 triệu đến $100+ triệu cho mặt nạ và đúc chip). | **Bằng 0** (Chỉ cần mua chip FPGA bán sẵn trên thị trường). |
| **Giá Thành Mỗi Chip** | Rất rẻ khi sản xuất hàng loạt quy mô lớn (hàng triệu chip). | Cao trên mỗi đơn vị chip. |
| **Hiệu Năng & Tốc Độ** | Cao nhất, xung nhịp cực nhanh, tối ưu từng transistor. | Trung bình/Khá (do vướng đường kết nối lập trình được). |
| **Tối Ưu Năng Lượng** | Tiết kiệm điện năng tối đa. | Tiêu thụ nhiều điện năng hơn. |
| **Thời Gian Ra Mắt** | Lâu (từ vài tháng đến vài năm). | Nhanh (từ vài ngày đến vài tuần). |

---

## 2. Quy Trình Thiết Kế ASIC Flow Chi Tiết

ASIC Flow là quá trình chuyển đổi mã nguồn phần cứng do con người viết thành bản vẽ vật lý 2D để gửi sang các nhà máy đúc chip (Foundry như TSMC, Samsung, Intel) chế tạo ra con chip thực tế trên silicon.

```
[System Spec] -> [Mã RTL (Verilog/VHDL)] -> [Linting & CDC] -> [Mô Phỏng Pre-Synth]
                                                                        |
[GDSII / Tapeout] <- [Kiểm Tra Vật Lý] <- [P&R Định Vị & Đi Dây] <- [Tổng Hợp Logic & DFT]
```

### Bước 1: Xác Định Kiến Trúc & Đặc Tả Hệ Thống (System Specification)
- **Mục tiêu**: Xác định con chip sẽ làm gì, tốc độ xung nhịp bao nhiêu (MHz/GHz), công suất tiêu thụ bao nhiêu Watt, diện tích tối đa bao nhiêu $mm^2$, dùng các chuẩn giao tiếp nào (PCIe, USB, DDR).

### Bước 2: Viết Mã RTL (Register Transfer Level)
- **Mục tiêu**: Sử dụng các ngôn ngữ mô tả phần cứng như **Verilog**, **SystemVerilog**, hoặc **VHDL** để mô tả luồng dữ liệu giữa các thanh ghi (registers), bộ chọn (multiplexer), bộ cộng (adder) và máy trạng thái (FSM).

### Bước 3: Kiểm Tra Tĩnh Code (Linting & CDC)
- **Mục tiêu**: Phát hiện lỗi code sớm trước khi chạy mô phỏng nặng.
  - **Linting**: Công cụ quét mã nguồn RTL để phát hiện lỗi cú pháp, biến chưa khởi tạo, vô tình tạo chốt nhớ (latch), hoặc không đúng quy chuẩn coding.
  - **CDC (Clock Domain Crossing)**: Kiểm tra các đường tín hiệu truyền qua lại giữa các miền xung nhịp khác nhau để tránh hiện tượng **Metastability** (mạch rơi vào trạng thái không xác định).

### Bước 4: Mô Phỏng Chức Năng (Pre-Synthesis Simulation)
- **Mục tiêu**: Đảm bảo mã RTL hoạt động đúng logic theo yêu cầu thiết kế.
  - **Pre-synthesis**: Chạy mô phỏng trên chính file code RTL ban đầu bằng các kịch bản kiểm thử (Testbench/UVM).

### Bước 5: Tổng Hợp Logic (Logic Synthesis) & Chèn DFT
- **Mục tiêu**: Chuyển đổi mã RTL thành mạng cổng logic (**Gate-Level Netlist**) dựa trên thư viện cổng chuẩn (Standard Cell Library: AND, OR, DFF, MUX) của nhà máy đúc chip.
  - **Logic Synthesis**: Công cụ tổng hợp (như Synopsys Design Compiler, Cadence Genus) tối ưu hóa các hàm đại số Boole dựa trên ràng buộc thời gian, diện tích và công suất.
  - **Chèn DFT (Design for Testability)**: Tự động chèn thêm các chuỗi kiểm thử vật lý (**Scan Chain**) vào netlist để khi đúc chip xong có thể cắm máy test phát hiện chip bị đứt dây/lỗi sản xuất hay không.

### Bước 6: Kiểm Tra Sau Tổng Hợp (Post-Synthesis Verification & STA)
- **Mục tiêu**: Xác nhận mạch sau tổng hợp vẫn giữ đúng chức năng và đạt tốc độ.
  - **Post-Synthesis Netlist**: File văn bản chứa danh sách cổng logic và các đường nối giữa chúng.
  - **Post-Synthesis Simulation**: Chạy mô phỏng trên netlist cổng logic có kèm độ trễ ước tính (SDF).
  - **LEC (Logic Equivalence Checking)**: Kiểm tra toán học chứng minh mã RTL và Post-Synthesis Netlist giống hệt nhau về mặt chức năng.

### Bước 7: Thiết Kế Vật Lý (Physical Design / Place & Route - P&R)
- **Mục tiêu**: Chuyển Netlist cổng logic thành bản vẽ sắp xếp không gian 2D trên chip silicon.
  1. **Floorplanning**: Quy hoạch vị trí các chân I/O, đường cấp nguồn (VDD/GND), và các khối bộ nhớ SRAM.
  2. **Placement**: Sắp xếp hàng triệu cổng logic chuẩn vào các hàng trên mặt bằng chip.
  3. **CTS (Clock Tree Synthesis)**: Cấu trúc mạng phân phối xung nhịp bằng các bộ đệm (buffers) để xung nhịp đến tất cả thanh ghi cùng một lúc (giảm tối đa clock skew).
  4. **Routing**: Đi các đường dây kim loại thực tế kết nối các cổng logic với nhau qua nhiều lớp kim loại.

### Bước 8: Kiểm Tra Vật Lý & Đóng Sổ (Physical Verification & Signoff)
- **Mục tiêu**: Đảm bảo bản vẽ vật lý tuân thủ mọi quy tắc chế tạo và đạt chuẩn thời gian.
  - **Post-Implementation (Post-Layout)**: Trích xuất thông số điện dung, điện trở thực tế của đường dây kim loại (**SPEF file**).
  - **Post-Layout STA**: Kiểm tra thời gian tĩnh chính xác nhất dựa trên độ trễ dây dẫn thật.
  - **DRC (Design Rule Check)**: Kiểm tra khoảng cách tối thiểu giữa các đường kim loại xem có bị dính/chập dây theo quy định của nhà máy đúc chip không.
  - **LVS (Layout Versus Schematic)**: Kiểm tra sơ đồ hình học vật lý có khớp 100% với netlist cổng logic không.

### Bước 9: Tapeout (Xuất File GDSII / OASIS)
- **Mục tiêu**: Xuất file bản vẽ nhị phân cuối cùng (**GDSII** hoặc **OASIS**) gửi sang nhà máy (Foundry) để tiến hành khắc quang đúc ra chip silicon thực tế.

---

## 3. Quy Trình Thiết Kế FPGA Flow Chi Tiết

Khác với ASIC, FPGA là con chip đã được sản xuất sẵn. Trong lòng FPGA chứa sẵn hàng trăm nghìn khối phần cứng lập trình được: **Look-Up Table (LUT)**, **Flip-Flop (FF)**, **Block RAM (BRAM)**, và khối nhân **DSP Slice**.

```
[Mã RTL] -> [Linting] -> [Mô Phỏng RTL] -> [Synthesis (Đổi thành LUT)] -> [P&R (Đặt & Đi dây)] -> [Tạo Bitstream (.bit)] -> [Nạp Chip FPGA]
```

1. **Viết Mã RTL & Linting**: Viết Verilog/SystemVerilog tối ưu cho cấu trúc FPGA.
2. **Mô Phỏng Pre-Synthesis**: Chạy mô phỏng dạng sóng để kiểm tra đúng logic phần mềm.
3. **FPGA Synthesis**: Công cụ (như Xilinx Vivado, Intel Quartus) dịch mã RTL thành các phần tử LUT, Flip-Flop, DSP48 của chip FPGA.
4. **Implementation (Place & Route / P&R)**:
   - **Translate / Map**: Nhóm các LUT và Flip-Flop thành các khối CLB (Configurable Logic Block).
   - **Place**: Đặt các khối CLB vào tọa độ vật lý cụ thể trên lưới chip FPGA.
   - **Route**: Bật/tắt các công tắc ma trận dây nối programmable interconnect để nối các khối lại với nhau.
5. **Phân Tích Post-Implementation (Timing Check)**: Kiểm tra xem mạch có bị vi phạm Setup Time / Hold Time theo tần số xung nhịp đã đặt trong file ràng buộc (`.xdc` / `.sdc`) hay không.
6. **Tạo File Bitstream**: Xuất ra file cấu hình nhị phân `.bit` hoặc `.bin`.
7. **Nạp Chip & Hardware Debug**: Nạp file `.bit` qua cổng JTAG vào bộ nhớ SRAM trên FPGA. Sử dụng công cụ phân tích logic tích hợp (như Xilinx ILA / ChipScope) để soi tín hiệu thực tế ngay trên phần cứng đang chạy.

---

## 4. Chuyên Sâu: Bản Chất Của LUT Trong FPGA (Look-Up Table, SRAM & LUTRAM)

Khối **LUT (Look-Up Table)** là trái tim của FPGA. Hiểu đúng bản chất của LUT sẽ giúp bạn làm chủ kiến trúc phần cứng FPGA.

### 4.1. Bản chất thực sự của LUT là gì?
- **Bản chất phần cứng**: LUT trong FPGA thực chất là một mảng các ô nhớ **SRAM nhỏ** đi kèm với một bộ chọn multiplexer ($2^N:1$).
- **Công thức dung lượng SRAM**: Một LUT có $N$ đầu vào (input pins) sẽ chứa bên trong đúng **$2^N$ ô nhớ SRAM (bits)**.
- **Ví dụ thực tế trong FPGA AMD / Xilinx**:
  - **LUT4** (trong các dòng FPGA cũ như Spartan-3 / Virtex-4): Có $N = 4$ đầu vào ($I_0 \dots I_3$) $\rightarrow$ Chứa $2^4 = 16$ bits SRAM bên trong.
  - **LUT6** (trong các dòng FPGA AMD/Xilinx 7-Series, UltraScale, Versal): Có $N = 6$ đầu vào ($I_0 \dots I_5$) $\rightarrow$ Chứa $2^6 = 64$ bits SRAM bên trong. Một LUT6 có thể thực hiện **BẤT KỲ** hàm Boole nào có 6 đầu vào!

```
                    Mô hình phần cứng bên trong 1 LUT 4-Input (LUT4)
                    
Ô nhớ SRAM (16 bits)          Bộ Chọn Multiplexer (16:1)          Đầu ra
+-------------------+        +---------------------------+        +---+
| SRAM[0]  = 0      |------->|                           |        |   |
| SRAM[1]  = 1      |------->|                           |------->| Y |
| SRAM[2]  = 1      |------->|                           |        |   |
| ...               |        | Inputs: I0, I1, I2, I3    |        +---+
| SRAM[15] = 0      |------->| (Đóng vai trò đường Select)|
+-------------------+        +---------------------------+
```

### 4.2. Tại sao xét riêng LUT là Mạch Tổ Hợp, nhưng xét TOÀN MẠCH lại là Mạch Tuần Tự?

Nhiều người mới học thường thắc mắc: *"Tại sao LUT chứa ô nhớ SRAM lưu trữ dữ liệu, nhưng xét đầu ra LUT lại là Mạch Tổ Hợp (Combinational), còn xét toàn mạch FPGA lại là Mạch Tuần Tự (Sequential)?"*

#### A. Khi xét ĐƠN LẺ bản thân khối LUT $\rightarrow$ Là MẠCH TỔ HỢP (Combinational Logic)
- Khi bạn thay đổi các tín hiệu đầu vào $I_0 \dots I_{N-1}$, đầu ra $Y$ của LUT sẽ thay đổi ngay lập tức dựa trên bảng truth table lưu trong các ô SRAM.
- Dữ liệu trong SRAM đã được nạp cố định lúc khởi động và **KHÔNG THAY ĐỔI** trong suốt quá trình chạy.
- Không có đường phản hồi (feedback loop) và không có tín hiệu Xung Nhịp (Clock) nào điều khiển việc lấy đầu ra này của LUT.
- 👉 **Vì đầu ra $Y$ chỉ phụ thuộc hoàn toàn vào tổ hợp các tín hiệu đầu vào ngay tại thời điểm đó $\rightarrow$ Bản thân khối LUT là Mạch Tổ Hợp.**

#### B. Khi xét TOÀN MẠCH thiết kế FPGA $\rightarrow$ Lại là MẠCH TUẦN TỰ (Sequential Logic)
Trong một hệ thống kỹ thuật số thực tế (như CPU, máy trạng thái FSM, bộ đếm), mạch không chỉ có tính toán mà bắt buộc phải **lưu trữ trạng thái theo thời gian**:
1. **Sau mỗi khối LUT luôn có Flip-Flop (FF) đi kèm:** Trong một ô phần tử logic FPGA (Slice/CLB), đầu ra của LUT được nối trực tiếp vào đầu vào của một **Flip-Flop (FF)** kế bên.
2. **Phối hợp hoạt động:** 
   - Khối **LUT** đảm nhận tính toán giá trị logic cho trạng thái tiếp theo (**Next State Logic**).
   - Khối **Flip-Flop** chờ cạnh lên của xung nhịp (`posedge clk`) để chốt và lưu giữ giá trị đó làm trạng thái hiện tại (**Current State**).
3. 👉 **Do đó, sự phối hợp giữa LUT (Tổ hợp) + Flip-Flop (Chốt theo Clock) tạo nên MẠCH TUẦN TỰ cho toàn bộ hệ thống FPGA.**

```
                       CẤU TRÚC 1 SLICE TRONG FPGA
  +-------------------------------------------------------------------+
  |                                                                   |
  |   Tín hiệu vào                                                    |
  |   (Inputs) ----> +----------------+                               |
  |                  |    LUT6        |  Đầu ra tổ hợp (O6)           |
  |                  | (Tổ hợp SRAM) |--------------------+          |
  |                  +----------------+                    |          |
  |                                                        v          |
  |                                                 +--------------+  |
  |   Clock -------------->------------------------>|  Flip-Flop   |  |
  |                                                 | (Thanh ghi D)|--+---> Đầu ra tuần tự (Q)
  |                                                 +--------------+  |
  +-------------------------------------------------------------------+
```

### 4.3. Tại sao ô nhớ LUT phải là SRAM? (Bí mật giúp EDA Tool tái cấu trúc phần cứng)

Tại sao nhà sản xuất FPGA không đúc cứng (hardwire) các cổng logic bằng kim loại như ASIC mà lại dùng các ô nhớ SRAM?

- **Bản chất của việc Cấu Hình Phần Cứng:**  
  Nếu các cổng logic bị khóa cứng trên silicon như ASIC, mỗi khi bạn sửa 1 dòng code Verilog trong EDA Tool (Vivado/Quartus), bạn sẽ phải vứt con chip đi và tốn hàng triệu USD đúc chip mới.
- **Vai trò của SRAM:**  
  - SRAM là bộ nhớ ghi/xóa được bằng điện áp.
  - Khi bạn biên dịch code Verilog mới, EDA Tool tổng hợp ra bảng Truth Table mới $\rightarrow$ Xuất ra file **Bitstream** nhị phân.
  - Khi nạp file Bitstream vào FPGA, các giá trị nhị phân mới sẽ **ghi đè (overwrite) vào các ô SRAM của LUT**. Ngay lập tức, con chip biến thành một mạch điện hoàn toàn mới mà không cần đụng một mũi khoan hay sợi dây vật lý nào!
- **Tại sao tắt điện FPGA lại mất cấu hình?**  
  Vì các ô nhớ LUT là **SRAM** (bộ nhớ tạm thời - Volatile Memory), khi tắt nguồn điện, toàn bộ dữ liệu trong SRAM sẽ bị xóa sạch. Do đó, bo mạch FPGA luôn cần một chip nhớ phụ (**SPI Flash**) để lưu file Bitstream và nạp lại vào SRAM mỗi khi bật nguồn.

> 💡 **Tóm tắt ẩn dụ:**
> - **ASIC:** Giống như **Sách In Mực Cố Định** – Không thể sửa chữ sau khi đã in.
> - **FPGA:** Giống như **Màn Hình Bảng Điện Tử (dùng SRAM)** – Thay đổi nội dung hiển thị (cấu trúc mạch) liên tục tùy theo file Bitstream bạn gửi vào!

### 4.4. Ngoại lệ: LUTRAM (Distributed RAM) là gì?
Thông thường, bạn không thể ghi dữ liệu vào các ô nhớ SRAM của LUT khi chip đang chạy. Tuy nhiên, trong kiến trúc FPGA của AMD/Xilinx, có các khối Slice đặc biệt gọi là **SLICEM (Memory Slice)**.

- **Khái niệm LUTRAM**: Trong khối SLICEM, phần cứng được thiết kế thêm các đường dây ghi (Write Enable, Write Clock, Write Data). Cho phép mạch điện **ghi dữ liệu mới vào các ô SRAM của LUT ngay trong quá trình chip đang chạy (Runtime)**.
- Khi hoạt động ở chế độ này, LUT biến thành một bộ nhớ RAM dung lượng nhỏ rải rác trên khắp bề mặt chip, gọi là **LUTRAM** (hoặc **Distributed RAM** - RAM phân tán).
- **Ứng dụng của LUTRAM**:
  - Làm các bộ đệm FIFO nhỏ (vài chục đến vài trăm bits).
  - Làm thanh ghi dịch (**SRL16 / SRL32** - Shift Register LUT).
  - Tiết kiệm bộ nhớ khối **Block RAM (BRAM)** lớn cho các tác vụ lưu trữ nặng hơn.

---

## 5. Giải Thích Các Thuật Ngữ Cốt Lõi (Glossary)

### Pre-Synthesis vs. Post-Synthesis là gì?
- **Pre-Synthesis (Trước tổng hợp)**: Là giai đoạn thiết kế **trước khi** biên dịch mã nguồn thành cổng logic. Bạn đang làm việc trực tiếp với mã **RTL** (`if-else`, `always @`, `assign`). Mô phỏng nhanh, dễ sửa lỗi logic.
- **Post-Synthesis (Sau tổng hợp)**: Là giai đoạn **sau khi** công cụ đã dịch mã RTL thành mạng cổng logic (**Gate-level Netlist** gồm `AND2X1`, `DFFX2`...). Mô phỏng chậm hơn nhưng bắt đầu có độ trễ ước tính của cổng logic.

### Pre-Implementation vs. Post-Implementation là gì?
- **Pre-Implementation (Trước thực thi/P&R)**: Mạch đã ở dạng netlist cổng logic nhưng **chưa được sắp xếp vị trí và chưa đi dây vật lý**. Độ trễ đường dây chỉ là ước tính sơ bộ.
- **Post-Implementation (Sau thực thi/P&R)**: Mạch **đã được đặt vị trí cụ thể và đi dây kim loại thực tế**. Độ trễ đường dây được trích xuất chính xác từ mô hình điện dung/điện trở (RC parasitics) của dây kim loại thật.

### Linting & CDC là gì?
- **Linting**: Quá trình kiểm tra tĩnh mã nguồn HDL (Verilog/VHDL) mà **không cần chạy mô phỏng**. Giúp bắt các lỗi như: biến khai báo xong không dùng, gán thiếu bit, vô tình tạo ra chốt nhớ (unintentional latch), hay xung đột kiểu dữ liệu.
- **CDC (Clock Domain Crossing)**: Việc kiểm tra các đường truyền tín hiệu từ miền xung nhịp A sang miền xung nhịp B. Nếu không có mạch đồng bộ (như 2-flip-flop synchronizer hay Asynchronous FIFO), tín hiệu sẽ bị hiện tượng **Metastability** gây ra lỗi ngẫu nhiên cực kỳ nguy hiểm.

### TCL (Tool Command Language) là gì?
- **TCL** (đọc là *"tickle"*): Là ngôn ngữ kịch bản tiêu chuẩn được **tất cả** các công cụ thiết kế vi mạch (EDA tools) như Synopsys Design Compiler, Cadence Innovus, Xilinx Vivado, Intel Quartus sử dụng. Kỹ sư dùng TCL để viết script tự động hóa toàn bộ luồng chạy mà không cần bấm tay trên giao diện đồ họa GUI.

### DFT (Design for Testability) là gì?
- Là việc thiết kế thêm phần cứng chuyên dụng vào chip ASIC **chỉ để phục vụ việc kiểm tra lỗi sản xuất**.
  - **Scan Chain**: Nối tất cả các Flip-Flop thành một chuỗi dịch dài để đẩy dữ liệu test vào và đọc kết quả ra.
  - **BIST (Built-In Self-Test)**: Mạch tự kiểm tra tích hợp sẵn bên trong chip (như MBIST để kiểm tra RAM).

### STA (Static Timing Analysis) là gì?
- **Phân tích thời gian tĩnh**: Là phương pháp kiểm tra toán học xem tất cả các đường truyền tín hiệu trong chip có thỏa mãn điều kiện thời gian (**Setup Time** và **Hold Time**) hay không mà **không cần chạy mô phỏng dạng sóng**. STA chạy cực kỳ nhanh và kiểm tra được 100% mọi đường truyền trong thiết kế.

### Equivalence Checking / Formal Verification là gì?
- Là phương pháp chứng minh toán học (như công cụ LEC - Logic Equivalence Checking) rằng hai phiên bản thiết kế (ví dụ: mã RTL ban đầu và Netlist sau tổng hợp) hoạt động hoàn toàn giống hệt nhau 100% về mặt chức năng logic mà không cần chạy bài test mô phỏng nào.

### Netlist, Standard Cells, GDSII & Bitstream là gì?
- **Netlist**: File văn bản mô tả danh sách các linh kiện (cổng logic hoặc LUT) và mạng lưới đường dây nối giữa các chân của chúng.
- **Standard Cells (Cổng chuẩn)**: Các khối logic cơ bản (AND, OR, NAND, DFF, MUX) do nhà máy đúc chip cấp sẵn trong thư viện công nghệ (như 7nm, 28nm).
- **GDSII / OASIS**: Định dạng file đồ họa 2D cuối cùng chứa bản vẽ các lớp khẩu độ (mask layers) gửi đi đúc chip ASIC.
- **Bitstream**: File nhị phân chứa các bit cấu hình nạp vào RAM của FPGA để bật/tắt các công tắc nối đường dây và nạp bảng giá trị cho LUT.

---

## 6. Sơ Đồ Tóm Tắt Luồng Thiết Kế

```
+-------------------------------------------------------------------------+
|                              MÃ RTL                                     |
|                      (Verilog / SystemVerilog)                          |
+-------------------------------------------------------------------------+
                                    |
          +-------------------------+-------------------------+
          |                                                   |
          v                                                   v
+-------------------+                               +-------------------+
|    ASIC FLOW      |                               |    FPGA FLOW      |
+-------------------+                               +-------------------+
          |                                                   |
          v                                                   v
  [Linting & CDC]                                     [Linting & CDC]
          |                                                   |
          v                                                   v
 [Mô Phỏng Pre-Synth (RTL)]                          [Mô Phỏng Pre-Synth (RTL)]
          |                                                   |
          v                                                   v
[Tổng Hợp Logic & Chèn DFT]                         [FPGA Synthesis (LUTs)]
          |                                                   |
          v                                                   v
[Mô Phỏng Post-Synth & LEC]                         [Implementation (P&R)]
          |                                                   |
          v                                                   v
[Floorplan / Place / CTS / Route]                 [Post-Imp STA / Timing Check]
          |                                                   |
          v                                                   v
[Trích Xuất Ký Sinh Post-Imp (SPEF)]                [Tạo File Bitstream (.bit)]
          |                                                   |
          v                                                   v
   [Kiểm Tra DRC / LVS]                               [Nạp FPGA qua JTAG]
          |
          v
 [Tapeout File GDSII]
```

---
*Tài liệu tổng hợp dành cho sinh viên và kỹ sư tìm hiểu thiết kế vi mạch ASIC & FPGA.*
