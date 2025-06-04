from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, abort, jsonify
from flask_socketio import SocketIO, emit
import os
from werkzeug.utils import secure_filename
import hashlib
from datetime import datetime
from functools import wraps
import json

import sys
import codecs

# --- Cấu hình đầu ra console thành UTF-8 ---
# Quan trọng để hiển thị tiếng Việt có dấu trong terminal/console mà không bị lỗi UnicodeEncodeError.
if sys.stdout.encoding != 'utf-8':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer)

app = Flask(__name__)
# RẤT QUAN TRỌNG: Thay đổi SECRET_KEY này trong môi trường production!
# Đây là khóa dùng để mã hóa session và giữ an toàn dữ liệu người dùng.
app.config['SECRET_KEY'] = 'a_very_secret_and_long_key_that_is_hard_to_guess_12345'
# Giới hạn kích thước file tải lên là 50MB.
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  

# --- Định nghĩa đường dẫn cơ sở của ứng dụng ---
# BASE_DIR sẽ là đường dẫn tuyệt đối đến thư mục chứa file app.py này.
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# --- Cấu hình thư mục tải lên (UPLOAD_FOLDER) sử dụng đường dẫn tuyệt đối ---
# Điều này đảm bảo thư mục 'uploads' luôn được tạo và sử dụng đúng vị trí,
# tránh các lỗi do đường dẫn tương đối bị hiểu sai Working Directory.
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'uploads')

socketio = SocketIO(app)

# --- Quản lý dữ liệu (thay thế Database mô phỏng bằng file JSON) ---

# Định nghĩa đường dẫn đầy đủ cho file 'users.json' và 'files.json'.
# Chúng sẽ được lưu TRONG thư mục 'uploads' để quản lý tập trung.
USERS_FILE = os.path.join(app.config['UPLOAD_FOLDER'], 'users.json')
FILES_DB_FILE = os.path.join(app.config['UPLOAD_FOLDER'], 'files.json')

def load_data(filepath):
    """
    Tải dữ liệu từ file JSON.
    Nếu file không tồn tại hoặc rỗng, nó sẽ tạo một file JSON rỗng và trả về dictionary rỗng.
    Điều này giúp ngăn chặn lỗi khi ứng dụng chạy lần đầu hoặc sau khi file bị xóa.
    """
    # Đảm bảo thư mục cha (UPLOAD_FOLDER) tồn tại trước khi tạo file mới.
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump({}, f) # Ghi một dictionary rỗng vào file.
        return {}
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_data(filepath, data):
    """
    Lưu dữ liệu vào file JSON.
    Đảm bảo thư mục cha tồn tại trước khi ghi file.
    """
    os.makedirs(os.path.dirname(filepath), exist_ok=True) 
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False) # indent=4 giúp file JSON dễ đọc hơn.

def get_users():
    return load_data(USERS_FILE)

def save_users(users_data):
    save_data(USERS_FILE, users_data)

def get_files_db():
    return load_data(FILES_DB_FILE)

def save_files_db(files_db_data):
    save_data(FILES_DB_FILE, files_db_data)

# --- Decorator kiểm tra đăng nhập ---
# Hàm "trang trí" này dùng để bảo vệ các route yêu cầu người dùng phải đăng nhập.
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Vui lòng đăng nhập để truy cập trang này.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- Helper function để định dạng kích thước file (Jinja2 Filter) ---
# Hàm này được đăng ký làm bộ lọc trong Jinja2 để hiển thị kích thước file dễ đọc hơn (KB, MB, GB).
@app.template_filter('filesizeformat')
def filesizeformat_filter(value):
    if value is None:
        return '0 Bytes'
    bytes_val = float(value)
    if bytes_val < 1024:
        return f"{bytes_val:.0f} Bytes"
    elif bytes_val < 1024**2:
        return f"{bytes_val / 1024:.2f} KB"
    elif bytes_val < 1024**3:
        return f"{bytes_val / (1024**2):.2f} MB"
    else:
        return f"{bytes_val / (1024**3):.2f} GB"

# --- Các Route của ứng dụng ---

@app.route('/')
def home():
    # Chuyển hướng đến dashboard nếu đã đăng nhập, ngược lại đến trang đăng nhập.
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Nếu đã đăng nhập, chuyển hướng ngay lập tức để tránh đăng nhập lại.
    if 'username' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        users_data = get_users()

        if username in users_data and users_data[username]['password'] == password:
            session['username'] = username
            flash(f'Chào mừng, {users_data[username]["name"]}! Đăng nhập thành công.', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Tên đăng nhập hoặc mật khẩu không đúng.', 'danger')

    return render_template('login.html')

@app.route('/logout')
@login_required # Chỉ cho phép đăng xuất nếu đã đăng nhập.
def logout():
    session.pop('username', None) # Xóa session của người dùng.
    flash('Bạn đã đăng xuất thành công.', 'info')
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    # Nếu đã đăng nhập, chuyển hướng ngay lập tức.
    if 'username' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        name = request.form['name']
        users_data = get_users()

        if not username or not password or not name:
            flash('Vui lòng điền đầy đủ thông tin.', 'danger')
        elif username in users_data:
            flash('Tên đăng nhập đã tồn tại.', 'danger')
        elif len(username) < 4:
            flash('Tên đăng nhập phải có ít nhất 4 ký tự.', 'danger')
        elif len(password) < 6:
            flash('Mật khẩu phải có ít nhất 6 ký tự.', 'danger')
        else:
            users_data[username] = {'password': password, 'name': name}
            save_users(users_data)
            flash('Đăng ký thành công! Vui lòng đăng nhập.', 'success')
            return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/dashboard')
@login_required # Chỉ cho phép truy cập dashboard nếu đã đăng nhập.
def dashboard():
    current_user = session['username']
    files_db = get_files_db()
    users_data = get_users()
    
    user_files = []
    for file_id, file_data in files_db.items():
        # Chỉ hiển thị file nếu người dùng là chủ sở hữu hoặc được chia sẻ với họ.
        if file_data['owner'] == current_user or current_user in file_data.get('shared_with', []):
            user_files.append({
                'id': file_id,
                'name': file_data['name'], # Tên gốc của file để hiển thị.
                'size': file_data['size'],
                'upload_time': file_data['upload_time'],
                'owner': file_data['owner'],
                'hash': file_data['hash'],
                'shared_with': file_data.get('shared_with', [])
            })

    # Sắp xếp file theo thời gian tải lên mới nhất.
    user_files.sort(key=lambda x: datetime.strptime(x['upload_time'], "%Y-%m-%d %H:%M:%S"), reverse=True)
    
    return render_template('dashboard.html', files=user_files, users=users_data)

@app.route('/upload', methods=['GET', 'POST'])
@login_required # Chỉ cho phép tải lên file nếu đã đăng nhập.
def upload():
    current_user = session['username']
    users_data = get_users() # Lấy danh sách người dùng để hiển thị trên form chia sẻ.

    if request.method == 'POST':
        if 'file' not in request.files:
            flash('Không có file được chọn.', 'danger')
            return redirect(request.url)

        file = request.files['file']
        if file.filename == '':
            flash('Không có file được chọn.', 'danger')
            return redirect(request.url)

        if file:
            # Lấy tên file gốc từ client. Ví dụ: "my_document.txt" hoặc "image"
            original_client_filename = file.filename
            
            # Tách tên file và phần mở rộng gốc.
            # Ví dụ: ("my_document", ".txt") hoặc ("image", "")
            base_name, original_extension = os.path.splitext(original_client_filename)
            
            # Làm sạch phần tên cơ sở (không có đuôi) bằng secure_filename.
            cleaned_base_name = secure_filename(base_name)
            
            # Đảm bảo phần mở rộng cũng an toàn và sử dụng lại phần mở rộng gốc.
            final_extension = secure_filename(original_extension) if original_extension else ""

            # Tạo tên file duy nhất trên server bằng cách thêm timestamp.
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
            
            # Ghép timestamp với tên cơ sở đã làm sạch VÀ phần mở rộng gốc.
            stored_filename_on_server = f"{timestamp}_{cleaned_base_name}{final_extension}"
            
            # Xây dựng đường dẫn file ĐẦY ĐỦ để lưu file vật lý vào thư mục 'uploads'.
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], stored_filename_on_server)

            try:
                file.save(filepath) # Lưu file vật lý vào thư mục 'uploads'.

                # Tính toán hash SHA-256 của file đã lưu để kiểm tra tính toàn vẹn sau này.
                sha256_hash = hashlib.sha256()
                with open(filepath, "rb") as f:
                    for byte_block in iter(lambda: f.read(4096), b""):
                        sha256_hash.update(byte_block)
                file_hash = sha256_hash.hexdigest()

                # Lấy danh sách người dùng được chia sẻ từ form.
                shared_users_list = request.form.getlist('shared_users')
                # Lọc bỏ người dùng hiện tại khỏi danh sách chia sẻ và chỉ giữ lại các user hợp lệ.
                shared_users_list = [u for u in shared_users_list if u != current_user and u in users_data]

                # Tạo một ID file duy nhất để định danh trong database (files.json).
                file_id = hashlib.md5(f"{stored_filename_on_server}{datetime.now()}".encode()).hexdigest()
                
                files_db = get_files_db()
                files_db[file_id] = {
                    'id': file_id,
                    'name': original_client_filename,    # Tên gốc của file (để hiển thị cho người dùng).
                    'stored_name': stored_filename_on_server, # Tên file đã được đổi (tên file vật lý trên server).
                    'size': os.path.getsize(filepath),
                    'hash': file_hash,
                    'upload_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'owner': current_user,
                    'shared_with': shared_users_list
                }
                save_files_db(files_db) # Lưu thông tin file vào files.json.

                flash('File đã được tải lên thành công!', 'success')
                return redirect(url_for('dashboard'))
            except Exception as e:
                flash(f'Lỗi khi tải file lên: {e}', 'danger')
                # Xóa file vật lý khỏi server nếu có lỗi xảy ra sau khi lưu.
                if os.path.exists(filepath):
                    os.remove(filepath)
                return redirect(request.url)

    # Lấy danh sách người dùng để chia sẻ, loại trừ chính người dùng hiện tại.
    user_list_for_sharing = {u: data for u, data in users_data.items() if u != current_user}
    return render_template('upload.html', users=user_list_for_sharing, all_users=users_data)

@app.route('/download/<file_id>')
@login_required # Chỉ cho phép tải xuống nếu đã đăng nhập.
def download(file_id):
    files_db = get_files_db()
    if file_id in files_db:
        file_data = files_db[file_id]
        current_user = session['username']
        # Kiểm tra quyền: Người dùng hiện tại phải là chủ sở hữu hoặc được chia sẻ.
        if current_user == file_data['owner'] or current_user in file_data.get('shared_with', []):
            # Xây dựng lại đường dẫn file vật lý từ 'stored_name' và UPLOAD_FOLDER.
            actual_filepath = os.path.join(app.config['UPLOAD_FOLDER'], file_data['stored_name'])
            
            # Kiểm tra xem file vật lý có tồn tại trên đĩa không trước khi gửi.
            if os.path.exists(actual_filepath):
                # send_file sẽ gửi file về client với tên gốc đã được lưu.
                return send_file(actual_filepath, as_attachment=True, download_name=file_data['name'])
            else:
                flash('File không tồn tại trên máy chủ. Có thể đã bị di chuyển hoặc xóa.', 'danger')
                return redirect(url_for('dashboard'))
    
    flash('Bạn không có quyền truy cập file này hoặc file không tồn tại.', 'danger')
    return redirect(url_for('dashboard'))

@app.route('/file/<file_id>')
@login_required # Chỉ cho phép xem thông tin file nếu đã đăng nhập.
def file_info(file_id):
    files_db = get_files_db()
    users_data = get_users() # Lấy danh sách người dùng để hiển thị tên thật thay vì username.
    
    if file_id in files_db:
        file_data = files_db[file_id]
        current_user = session['username']
        # Kiểm tra quyền: Người dùng hiện tại phải là chủ sở hữu hoặc được chia sẻ.
        if current_user == file_data['owner'] or current_user in file_data.get('shared_with', []):
            # Xây dựng đường dẫn vật lý và kiểm tra sự tồn tại của file trên đĩa.
            actual_filepath = os.path.join(app.config['UPLOAD_FOLDER'], file_data['stored_name'])
            file_exists_on_disk = os.path.exists(actual_filepath) # Biến này sẽ được truyền vào template.

            # Lấy tên hiển thị của chủ sở hữu.
            owner_name = users_data.get(file_data['owner'], {}).get('name', file_data['owner'])
            
            # Lấy tên hiển thị của những người được chia sẻ.
            shared_with_names = []
            for user_id in file_data.get('shared_with', []):
                shared_with_names.append(users_data.get(user_id, {}).get('name', user_id))

            return render_template('file_info.html', 
                                   file=file_data, 
                                   owner_name=owner_name,
                                   shared_with_names=shared_with_names,
                                   file_exists_on_disk=file_exists_on_disk, # Truyền biến này vào template.
                                   users=users_data)
    
    flash('Bạn không có quyền xem thông tin file này hoặc file không tồn tại.', 'danger')
    return redirect(url_for('dashboard'))

# --- SocketIO event cho kiểm tra tính toàn vẹn file ---
@socketio.on('verify_file')
def handle_verify(data):
    file_id = data.get('file_id')
    
    files_db = get_files_db() # Tải lại dữ liệu file mới nhất để đảm bảo đồng bộ.
    
    if not file_id or file_id not in files_db:
        emit('verification_result', {
            'success': False,
            'message': 'File không tồn tại trên hệ thống hoặc ID không hợp lệ.'
        })
        return

    file_data = files_db[file_id]
    
    # Kiểm tra quyền truy cập qua session của người dùng hiện tại.
    current_user = session.get('username')
    if not current_user or (current_user != file_data['owner'] and current_user not in file_data.get('shared_with', [])):
        emit('verification_result', {
            'success': False,
            'message': 'Bạn không có quyền kiểm tra file này.'
        })
        return

    # Xây dựng đường dẫn file vật lý từ 'stored_name' và UPLOAD_FOLDER.
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file_data['stored_name'])

    if not os.path.exists(filepath):
        emit('verification_result', {
            'success': False,
            'message': 'File vật lý không tồn tại trên máy chủ. Vui lòng kiểm tra lại đường dẫn.'
        })
        return
        
    try:
        # Tính toán lại hash SHA-256 của file hiện tại trên đĩa.
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            # Đọc từng khối (block) để xử lý file lớn mà không tốn nhiều RAM.
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        current_hash = sha256_hash.hexdigest()
        
        # So sánh hash hiện tại với hash gốc được lưu trong files.json.
        if current_hash == file_data['hash']:
            emit('verification_result', {
                'success': True,
                'message': 'File nguyên vẹn. Hash khớp!',
                'current_hash': current_hash,
                'original_hash': file_data['hash']
            })
        else:
            emit('verification_result', {
                'success': False,
                'message': 'File đã bị thay đổi. Hash không khớp!',
                'current_hash': current_hash,
                'original_hash': file_data['hash']
            })
    except Exception as e:
        emit('verification_result', {
            'success': False,
            'message': f'Lỗi khi tính toán hash: {e}'
        })

if __name__ == '__main__':
    # Tạo một số người dùng mặc định nếu users.json trống.
    # Việc này sẽ chỉ xảy ra lần đầu tiên khi users.json chưa có dữ liệu.
    users_data = get_users()
    if not users_data:
        users_data['admin'] = {'password': 'adminpassword', 'name': 'Quản trị viên'}
        users_data['testuser'] = {'password': 'testpassword', 'name': 'Người dùng thử'}
        save_users(users_data)
        print("Đã tạo người dùng mặc định: admin/adminpassword, testuser/testpassword")

    # In thông báo khởi động ứng dụng (đã khắc phục lỗi hiển thị tiếng Việt trong console).
    print(f"Ứng dụng đang chạy tại: http://127.0.0.1:5000/")
    # Chạy ứng dụng Flask với SocketIO. debug=True cho phép tự động tải lại khi code thay đổi.
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)