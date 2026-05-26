class OodCore::Job::Adapters::FirecREST::ClusterFile

  attr_reader :path, :adapter

  def basename(*args) = path.basename(*args)
  def descend(*args, &block) = path.descend(*args, &block)
  def parent(*args) = path.parent(*args)
  def join(*args) = path.join(*args)
  def to_s = path.to_s

  def initialize(path, adapter)
    @adapter = adapter
    @path = path
  end

  def remote_type
    "cluster"
  end

  def raise_if_cant_access_directory_contents; end

  def directory?
    info = adapter.file_info(path)
    info.include?("directory") && !info.include?("symbolic link")
  end

  def ls
    files = adapter.list_files(path, show_hidden_files: true)
    files
      .select { |file| file["type"] == "-" || file["type"] == "d" }
      .map do |file|
        {
          id:         path.join(file["name"]),
          name:       file["name"],
          size:       file['size'],
          human_size: human_size(file),
          directory:  file["type"] == "d",
          date:       DateTime.parse(file['lastModified']).to_time.to_i,
          owner:      file["user"],
          mode:       '', # TODO: parse the mode
          dev:        0
        }
    rescue => e
      # Ignore file if parsing errors occur
      nil
    end.compact.sort_by { |p| p[:directory] ? 0 : 1 }
  end

  def human_size(file)
    size = file["size"].to_i
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    i = 0
    while size >= 1024 && i < units.length - 1
      size /= 1024.0
      i += 1
    end
    i == 0 ? "#{size} #{units[i]}" : "#{'%.1f' % size} #{units[i]}"
  end

  def can_download_as_zip?(*)
    [false, 'Downloading remote files as zip is currently not supported']
  end

  def editable?
    !directory?
  end

  def read(&block)
    adapter.download(path, &block)
  end

  def touch
    # FirecREST does not support 0-byte uploads; create a file with minimal content.
    adapter.upload(path, content: "\n")
  end

  def mkdir
    adapter.mkdir(path)
  end

  def write(content)
    adapter.upload(path, content:)
  end

  def handle_upload(tempfile)
    adapter.upload(path, source_path: tempfile)
  end

  def mime_type
    ""
  end

  def send_small_file(response, download:, type:)
    # Need to attempt to read before setting headers in case it is not a small file.
    data = read
    response.set_header('X-Accel-Buffering', 'no')
    response.sending_file = true
    response.set_header("Last-Modified", Time.now.httpdate)
    if download
      response.set_header("Content-Type", type) if type.present?
      response.set_header("Content-Disposition", "attachment")
    else
      response.set_header("Content-Type", Files.mime_type_for_preview(type)) if type.present?
      response.set_header("Content-Disposition", "inline")
    end
    begin
      response.stream.write(data)
      # Need to rescue exception when user cancels download.
    rescue ActionController::Live::ClientDisconnected => e
    ensure
      response.stream.close
    end
  end

  def send_large_file(controller, download:, type:)
    # Redirect user directly to the URL where file can be downloaded.
    external_url = adapter.xfer_download(path)
    controller.redirect_to external_url, :status => :see_other
  end

  def send_file(controller, download:, type:)
    # Assume file is small, fall back to the large file handling if it is not.
    begin
      send_small_file(controller.response, download: download, type: type)
    rescue StandardError => e
      send_large_file(controller, download: download, type: type)
    end
  end

  def to_str
    to_s
  end
end
