class OodCore::Job::Adapters::FirecREST::ClusterTransfer < Transfer

  attr_accessor :adapter

  class << self
    def transfers
      # all transfers stored in the Transfer class
      Transfer.transfers
    end

    def build(action:, files:, adapter:)

      if files.is_a?(Array)
        # rm action will want to provide an array of files
        # so if it is an Array we convert it to a hash:
        #
        # convert [a1, a2, a3] to {a1 => nil, a2 => nil, a3 => nil}
        files = Hash[files.map { |f| [f, nil] }].with_indifferent_access
      end

      self.new(action: action, files: files, adapter: adapter)
    end
  end

  # total number of bytes
  def steps
    1
  end

  def command_str
    ''
  end

  def perform
    self.status = OodCore::Job::Status.new(state: :running)
    self.started_at = Time.now.to_i

    # Transfer each file/directory indiviually
    files.each do |src, dst|
      if move?
        adapter.mv(src, dst)
      elsif copy?
        adapter.cp(src, dst)
      elsif remove?
        adapter.rm(src)
      else
        raise StandardError, "Unknown action: #{action.inspect}"
      end
    rescue => e
      # TODO: catch more rclone specific errors here, i.e. if the access keys are invalid it would make
      # sense to not attempt to transfer the rest of the files
      errors.add :base, "Error when transferring #{src}: #{e.message}"
    end
  rescue => e
    Rails.logger.info(e.backtrace.join("\n"))
    errors.add :base, e.message
  ensure
    self.status = OodCore::Job::Status.new(state: :completed)
  end

  def from
    File.dirname(files.keys.first) if files.keys.first
  end

  def to
    File.dirname(files.values.first) if files.values.first
  end

  def target_dir
    # directory where files are being moved/copied to OR removed from
    if action == 'rm'
      Pathname.new(from).cleanpath if from
    else
      Pathname.new(to).cleanpath if to
    end
  end

  def synchronous?
    false
  end
end

