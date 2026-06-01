require 'etc'
require 'json'
require 'jwt'
require 'net/http'
require 'net/http/post/multipart'
require "ood_core/refinements/hash_extensions"
require "ood_core/refinements/array_extensions"
require "ood_core/job/adapters/helper"
require 'time'
require 'uri'

require 'rubygems/package'

module OodCore
  module Job
    class Factory
      using Refinements::HashExtensions

      # Build the FirecREST adapter from a configuration
      def self.build_firecrest(config)
        c = config.to_h.symbolize_keys
        machine   = c.fetch(:machine, nil)
        endpoint  = c.fetch(:endpoint, nil)
        firecrest = Adapters::FirecREST::Batch.new(machine: machine, endpoint: endpoint)
        Adapters::FirecREST.new(firecrest: firecrest)
      end
    end

    module Adapters
      # An adapter object that describes the communication with a Slurm
      # resource manager for job management via the FirecREST v2 API.
      class FirecREST < Adapter
        using Refinements::HashExtensions
        using Refinements::ArrayExtensions

        # ClusterFile and ClusterTransfer depend on OOD Rails app classes
        # (Transfer, ApplicationController, Rails.logger) and are only available
        # in a full OOD environment.
        begin
          require "ood_core/job/adapters/firecrest/cluster_file"
          require "ood_core/job/adapters/firecrest/cluster_transfer"
        rescue NameError
        end

        # @api private
        class Batch

          attr_reader :machine
          attr_reader :endpoint

          class Error < StandardError; end
          class TokenError < Error; end
          class HttpError < Error; end
          class FileTransferError < Error; end

          def initialize(machine: nil, endpoint: nil)
            @machine       = machine && machine.to_s
            @firecrest_uri = endpoint && endpoint.to_s
            @client_id     = ENV['FIRECREST_CLIENT_ID']
            @client_secret = ENV['FIRECREST_CLIENT_SECRET']
            @token_uri     = ENV['FIRECREST_TOKEN_URI']
            @token_cache   = {}
            @user_cache    = {}
          end

          # ---------- URL helpers ----------

          def compute_url(path)
            "#{@firecrest_uri}/compute/#{@machine}/#{path}"
          end

          def filesystem_url(path)
            "#{@firecrest_uri}/filesystem/#{@machine}/#{path}"
          end

          def status_url(path)
            "#{@firecrest_uri}/status/#{@machine}/#{path}"
          end

          # ---------- Job management ----------

          # Submit a job script to the batch server.
          # @param script_content [String] the script content
          # @param working_directory [String] working directory for the job
          # @param name [String, nil] job name
          # @param account [String, nil] account to charge
          # @param standard_output [String, nil] stdout file path
          # @param standard_error [String, nil] stderr file path
          # @param standard_input [String, nil] stdin file path
          # @return [String] the job id
          def submit_job(script_content, working_directory: "/tmp", name: nil,
                         account: nil, standard_output: nil, standard_error: nil,
                         standard_input: nil)
            job = {
              script:           script_content,
              workingDirectory: working_directory
            }
            job[:name]           = name            if name
            job[:account]        = account         if account
            job[:standardOutput] = standard_output if standard_output
            job[:standardError]  = standard_error  if standard_error
            job[:standardInput]  = standard_input  if standard_input

            response = http_post_json(compute_url("jobs"), headers: build_headers, data: { job: job })
            JSON.parse(response.body)["jobId"]
          end

          # Cancel a job.
          # @param job_id [String] the job id
          def delete_job(job_id)
            http_delete(compute_url("jobs/#{job_id}"), headers: build_headers)
          end

          # Retrieve all jobs (active and completed).
          # @param job_ids [Array<String>] optional list of job ids to filter
          # @return [Array<Hash>] list of job objects
          def get_jobs(job_ids: [])
            params = {}
            params["jobs"] = job_ids.join(",") unless job_ids.empty?
            response = http_get(compute_url("jobs"), headers: build_headers, params: params)
            JSON.parse(response.body)["jobs"] || []
          end

          # Retrieve a single job by id.
          # @param job_id [String] the job id
          # @return [Hash, nil] the job object or nil if not found
          def get_job(job_id)
            return nil if job_id.nil? || job_id.to_s.empty?
            response = http_get(compute_url("jobs/#{job_id}"), headers: build_headers, params: {})
            return nil if response.body.nil? || response.body.empty?
            JSON.parse(response.body)["jobs"]&.first
          rescue HttpError, JSON::ParserError
            nil
          end

          # Retrieve metadata for a job (script path, stdout, stderr, stdin paths).
          # @param job_id [String] the job id
          # @return [Hash, nil] the metadata object or nil
          def get_job_metadata(job_id)
            response = http_get(compute_url("jobs/#{job_id}/metadata"), headers: build_headers, params: {})
            JSON.parse(response.body)["jobs"]&.first
          rescue HttpError
            nil
          end

          # ---------- User info ----------

          # Get the current authenticated username.
          # @return [String] the username
          def user
            @user_cache[@machine] ||= begin
              response = http_get(status_url("userinfo"), headers: build_headers, params: {})
              JSON.parse(response.body)["user"]["name"]
            end
          end

          # Get the groups the current user belongs to.
          # @return [Array<String>] list of group names
          def get_groups
            response = http_get(status_url("userinfo"), headers: build_headers, params: {})
            JSON.parse(response.body)["groups"].map { |g| g["name"] }
          end

          # ---------- File operations ----------

          # Upload a file to the cluster.
          # @param target_path [String] destination path on the cluster
          # @param source_path [String, nil] local path of the file to upload
          # @param content [String, nil] content to upload as a file
          def upload(target_path, source_path: nil, content: nil)
            file = source_path || StringIO.new(content)
            begin
              mkdir(File.dirname(target_path.to_s), create_intermediate_dirs: true)
            rescue HttpError
              # Directory may already exist; proceed with upload
            end

            uri = URI(filesystem_url("ops/upload"))
            # The API treats `path` as the target directory; the filename comes
            # from the multipart upload's filename field.
            uri.query = URI.encode_www_form({ path: File.dirname(target_path.to_s) })

            opened = !file.is_a?(IO) && !file.is_a?(StringIO)
            io     = opened ? File.open(file) : (file.rewind; file)
            begin
              upload_io = Multipart::Post::UploadIO.new(io, 'application/octet-stream', File.basename(target_path.to_s))
              request = Net::HTTP::Post::Multipart.new("#{uri.path}?#{uri.query}", { "file" => upload_io })
              build_headers.each { |k, v| request[k] = v }
              request_with_retries(request, uri: uri)
            ensure
              io.close if opened
            end
          end

          # Stage job files to the cluster as a tar archive.
          def stage(src, dst)
            src_path = File.expand_path(src)
            files    = Dir.glob("#{src_path}/**/*").select { |e| File.file? e }.to_a
            require 'tempfile'
            tmpfile = Tempfile.new(['ood_stage', '.tar'])
            begin
              File.open(tmpfile.path, "wb") do |file|
                Gem::Package::TarWriter.new(file) do |tar|
                  files.each do |f|
                    rel_file = f.sub(/^#{Regexp::escape(src_path)}\/?/, '')
                    stat     = File.stat(f)
                    tar.add_file_simple(rel_file, stat.mode & 0777, stat.size) do |io|
                      IO.copy_stream(f, io)
                    end
                  end
                end
              end
              mkdir(dst.to_s, create_intermediate_dirs: true)
              upload(dst.to_s, source_path: tmpfile.path)
            ensure
              tmpfile.close
              tmpfile.unlink
            end
          end

          # View the contents of a file on the cluster.
          # @param file [String] path to the file
          # @return [String] file contents
          def view(file)
            response = http_get(filesystem_url("ops/view"), headers: build_headers, params: { path: file })
            JSON.parse(response.body)["output"]
          end

          # View the first lines of a file on the cluster.
          # @param target_path [String] path to the file
          # @return [String] file head contents
          def head(target_path)
            response = http_get(filesystem_url("ops/head"), headers: build_headers, params: { path: target_path })
            JSON.parse(response.body)["output"]
          end

          # List files in a directory on the cluster.
          # @param target_path [String] path to the directory
          # @param show_hidden_files [Boolean] whether to include hidden files
          # @return [Array<Hash>] list of file objects
          def list_files(target_path, show_hidden_files: false)
            params = { path: target_path, showHidden: show_hidden_files }
            response = http_get(filesystem_url("ops/ls"), headers: build_headers, params: params)
            JSON.parse(response.body)["output"]
          end

          # Get the type of a file or directory.
          # @param target_path [String] path to check
          # @return [String] file type string (e.g. "file", "directory")
          def file_info(target_path)
            response = http_get(filesystem_url("ops/file"), headers: build_headers, params: { path: target_path })
            JSON.parse(response.body)["output"]
          end

          # Download a file from the cluster, streaming to a block.
          # @param source_path [String] path to the file on the cluster
          def download(source_path, &block)
            http_get(filesystem_url("ops/download"), headers: build_headers, params: { path: source_path }) do |response|
              return response.read_body(&block)
            end
          end

          # Generate a pre-signed S3 download URL for a file on the cluster.
          # @param source_path [String] path to the file on the cluster
          # @return [String, nil] the pre-signed download URL
          def xfer_download(source_path)
            data = {
              sourcePath: source_path,
              transferDirectives: { transferMethod: "s3" }
            }
            response = http_post_json(filesystem_url("transfer/download"), headers: build_headers, data: data)
            JSON.parse(response.body).dig("transferDirectives", "downloadUrl")
          end

          # Create a directory on the cluster.
          # @param target_path [String] path to create
          # @param create_intermediate_dirs [Boolean] whether to create parent directories
          def mkdir(target_path, create_intermediate_dirs: false)
            body = { sourcePath: target_path, parent: create_intermediate_dirs }
            http_post_json(filesystem_url("ops/mkdir"), headers: build_headers, data: body)
          end

          # Move a file or directory on the cluster (async, polls for completion).
          # @param source_path [String] source path
          # @param target_path [String] destination path
          def mv(source_path, target_path)
            data = { sourcePath: source_path, targetPath: target_path }
            response = http_post_json(filesystem_url("transfer/mv"), headers: build_headers, data: data)
            transfer_job = JSON.parse(response.body)["transferJob"]
            wait_transfer_job(transfer_job)
          end

          # Copy a file or directory on the cluster (async, polls for completion).
          # @param source_path [String] source path
          # @param target_path [String] destination path
          def cp(source_path, target_path)
            data = { sourcePath: source_path, targetPath: target_path }
            response = http_post_json(filesystem_url("transfer/cp"), headers: build_headers, data: data)
            transfer_job = JSON.parse(response.body)["transferJob"]
            wait_transfer_job(transfer_job)
          end

          # Delete a file or directory on the cluster.
          # @param target_path [String] path to delete
          def rm(target_path)
            http_delete(filesystem_url("ops/rm"), headers: build_headers, params: { path: target_path })
          end

          # ---------- State helpers ----------

          STATE_MAP = {
            'BOOT_FAIL'     => :completed,
            'CANCELLED'     => :completed,
            'COMPLETED'     => :completed,
            'DEADLINE'      => :completed,
            'CONFIGURING'   => :queued,
            'COMPLETING'    => :running,
            'FAILED'        => :completed,
            'NODE_FAIL'     => :completed,
            'PENDING'       => :queued,
            'PREEMPTED'     => :suspended,
            'REVOKEDRV'     => :completed,
            'RUNNING'       => :running,
            'SPECIAL_EXIT'  => :completed,
            'STOPPED'       => :running,
            'SUSPENDED'     => :suspended,
            'TIMEOUT'       => :completed,
            'OUT_OF_MEMORY' => :completed
          }.freeze

          def slurm_state_to_ood_state(state)
            STATE_MAP.each { |key, val| return val if state.to_s.include?(key) }
            :undetermined
          end

          private

          # ---------- Transfer job polling ----------

          def wait_transfer_job(transfer_job, max_wait: 1800)
            job_id    = transfer_job["jobId"]
            error_log = transfer_job.dig("logs", "errorLog")
            deadline  = Time.now + max_wait
            wait      = 1

            loop do
              raise FileTransferError, "Transfer job #{job_id} timed out after #{max_wait}s" if Time.now > deadline

              job = get_job(job_id)
              unless job
                sleep(wait)
                wait = [wait * 2, 30].min
                next
              end

              state = job.dig("status", "state").to_s
              unless slurm_state_to_ood_state(state) == :completed
                sleep(wait)
                wait = [wait * 2, 30].min
                next
              end

              if state == "COMPLETED"
                log_content = head(error_log).to_s
                raise FileTransferError, "Error in file transfer. Details in #{error_log}" unless log_content.empty?
                return
              end

              raise FileTransferError, "Transfer job #{job_id} finished with status #{state}"
            end
          end

          # ---------- Auth ----------

          class Token
            attr_reader :token, :expiry

            def initialize(token)
              decoded = JWT.decode(token, nil, false)
              @expiry = Time.at(decoded[0]['exp'])
              @token  = token
            end

            def expired?
              Time.now >= expiry
            end

            def to_s
              token.to_s
            end
          end

          def token
            t = @token_cache[@machine]
            return t if t && !t.expired?

            uri  = URI(@token_uri)
            data = { grant_type: 'client_credentials', client_id: @client_id, client_secret: @client_secret }

            req = Net::HTTP::Post.new(uri)
            req['Content-Type'] = 'application/x-www-form-urlencoded'
            req.set_form_data(data)

            resp = Net::HTTP.start(uri.host, uri.port, use_ssl: uri.scheme == 'https') { |h| h.request(req) }
            raise TokenError, "Failed to obtain token: #{resp.body}" if resp.code.to_i != 200

            @token_cache[@machine] = Token.new(JSON.parse(resp.body)["access_token"])
          rescue => e
            raise TokenError, "Token error: #{e.message}"
          end

          def build_headers
            { 'Authorization' => "Bearer #{token}" }
          end

          # ---------- HTTP methods ----------

          def request_with_retries(request, uri: request.uri, max_retries: 5, &block)
            retries = 0
            begin
              Net::HTTP.start(uri.host, uri.port, use_ssl: uri.scheme == 'https',
                              open_timeout: 30, read_timeout: 120) do |http|
                http.request(request) do |response|
                  if response.code.to_i == 429
                    retry_after = response['RateLimit-Reset'].to_i
                    sleep(retry_after > 0 ? retry_after : 1)
                    retries += 1
                    raise RetryRequest
                  elsif response.code.to_i >= 400
                    raise HttpError, "Error: #{response.code}: #{response.body}"
                  elsif block_given?
                    yield response
                    return
                  else
                    response.read_body
                    return response
                  end
                end
              end
            rescue RetryRequest
              retry if retries <= max_retries
            rescue Net::ReadTimeout, Net::OpenTimeout, OpenSSL::SSL::SSLError => e
              retries += 1
              retry if retries <= max_retries
              raise HttpError, "Request failed after #{max_retries} retries: #{e.message}"
            end
            raise HttpError, "Maximum number of retries reached for #{request.uri}"
          end

          RetryRequest = Class.new(StandardError)

          def http_get(url, headers: {}, params: {}, max_retries: 5, &block)
            uri = URI(url)
            uri.query = URI.encode_www_form(params) unless params.empty?
            req = Net::HTTP::Get.new(uri)
            headers.each { |k, v| req[k] = v }
            request_with_retries(req, max_retries: max_retries, &block)
          end

          def http_post_json(url, headers: {}, data: {}, max_retries: 5)
            uri = URI.parse(url)
            req = Net::HTTP::Post.new(uri)
            req['Content-Type'] = 'application/json'
            req.body = data.to_json
            headers.each { |k, v| req[k] = v }
            request_with_retries(req, uri: uri, max_retries: max_retries)
          end

          def http_delete(url, headers: {}, params: {}, max_retries: 5)
            uri = URI(url)
            uri.query = URI.encode_www_form(params) unless params.empty?
            req = Net::HTTP::Delete.new(uri)
            headers.each { |k, v| req[k] = v }
            request_with_retries(req, max_retries: max_retries)
          end
        end

        # @api private
        # @param opts [#to_h] the options defining this adapter
        # @option opts [Batch] :firecrest The FirecREST batch object
        # @see Factory.build_firecrest
        def initialize(opts = {})
          o = opts.to_h.symbolize_keys
          @firecrest = o.fetch(:firecrest) { raise ArgumentError, "No firecrest object specified. Missing argument: firecrest" }
        end

        def cluster_file(path)
          ClusterFile.new(path, @firecrest)
        end

        def cluster_transfer(action:, files:)
          ClusterTransfer.build(action: action, files: files, adapter: @firecrest)
        end

        # Submit a job with the attributes defined in the job template instance.
        # @param script [Script] script object that describes the script and
        #   attributes for the submitted job
        # @param after [#to_s, Array<#to_s>] this job may be scheduled for
        #   execution at any point after dependent jobs have started execution
        # @param afterok [#to_s, Array<#to_s>] this job may be scheduled for
        #   execution only after dependent jobs have terminated with no errors
        # @param afternotok [#to_s, Array<#to_s>] this job may be scheduled for
        #   execution only after dependent jobs have terminated with errors
        # @param afterany [#to_s, Array<#to_s>] this job may be scheduled for
        #   execution after dependent jobs have terminated
        # @raise [JobAdapterError] if something goes wrong submitting a job
        # @return [String] the job id returned after successfully submitting a job
        # @see Adapter#submit
        def submit(script, after: [], afterok: [], afternotok: [], afterany: [])
          after      = Array(after).map(&:to_s)
          afterok    = Array(afterok).map(&:to_s)
          afternotok = Array(afternotok).map(&:to_s)
          afterany   = Array(afterany).map(&:to_s)

          # Build only the #SBATCH directives that have no dedicated API field.
          headers = ""
          headers << "#SBATCH --mail-user=#{script.email.join(",")}\n" unless script.email.nil?
          if script.email_on_started && script.email_on_terminated
            headers << "#SBATCH --mail-type ALL\n"
          elsif script.email_on_started
            headers << "#SBATCH --mail-type BEGIN\n"
          elsif script.email_on_terminated
            headers << "#SBATCH --mail-type END\n"
          elsif script.email_on_started == false && script.email_on_terminated == false
            headers << "#SBATCH --mail-type NONE\n"
          end
          headers << "#SBATCH --reservation #{script.reservation_id}\n" unless script.reservation_id.nil?
          headers << "#SBATCH --priority #{script.priority}\n"          unless script.priority.nil?
          headers << "#SBATCH -a #{script.job_array_request}\n"         unless script.job_array_request.nil?
          headers << "#SBATCH -t #{seconds_to_duration(script.wall_time)}\n" unless script.wall_time.nil?
          headers << "#SBATCH -p #{script.queue_name}\n"                unless script.queue_name.nil?
          headers << "#SBATCH --qos #{script.qos}\n"                    unless script.qos.nil?
          headers << "#SBATCH --dependency=after:#{after.join(":")}\n"         unless after.empty?
          headers << "#SBATCH --dependency=afterok:#{afterok.join(":")}\n"     unless afterok.empty?
          headers << "#SBATCH --dependency=afternotok:#{afternotok.join(":")}\n" unless afternotok.empty?
          headers << "#SBATCH --dependency=afterany:#{afterany.join(":")}\n"   unless afterany.empty?

          content = if script.content.to_s.start_with?('#!')
                      script.content.to_s.sub(/\A(#![^\n]*\n)/, "\\1\n#{headers}")
                    else
                      "#!/bin/bash -l\n\n#{headers}#{script.content}"
                    end

          working_directory = script.output_path ? File.dirname(script.output_path.to_s) : "/tmp"

          @firecrest.submit_job(
            content,
            working_directory: working_directory,
            name:              script.job_name,
            account:           script.accounting_id,
            standard_output:   script.output_path&.to_s,
            standard_error:    script.error_path&.to_s,
            standard_input:    script.input_path&.to_s
          )
        end

        def stage(src, dst)
          @firecrest.stage(src, dst)
        end

        # Retrieve info about active and total cpus, gpus, and nodes.
        # @return [ClusterInfo] information about cluster usage
        def cluster_info
          # TODO: FirecREST v2 has no node listing endpoint; returning nil values
          ClusterInfo.new(
            active_nodes:      nil,
            total_nodes:       nil,
            active_processors: nil,
            total_processors:  nil,
            active_gpus:       nil,
            total_gpus:        nil
          )
        end

        # Retrieve info for all jobs from the resource manager.
        # @raise [JobAdapterError] if something goes wrong getting job info
        # @return [Array<Info>] information describing submitted jobs
        # @see Adapter#info_all
        def info_all(attrs: nil)
          @firecrest.get_jobs.map { |v| parse_job_info(v) }
        end

        # Retrieve info for all jobs for a given owner from the resource manager.
        # @param owner [#to_s, Array<#to_s>] the owner(s) of the jobs
        # @raise [JobAdapterError] if something goes wrong getting job info
        # @return [Array<Info>] information describing submitted jobs
        def info_where_owner(owner, attrs: nil)
          # FirecREST v2 returns only the current user's jobs; owner param is ignored
          @firecrest.get_jobs.map { |v| parse_job_info(v) }
        end

        # Extended Info class that carries interactive app connection info.
        class FirecRESTJobInfo < OodCore::Job::Info
          attr_reader :ood_connection_info

          def initialize(options)
            @ood_connection_info = options[:ood_connection_info]
            super(**options)
          end

          def respond_to?(name, include_private = false)
            return false if name == :ood_connection_info && ood_connection_info.nil?
            super
          end
        end

        # Retrieve job info from the resource manager.
        # @param id [#to_s] the id of the job
        # @raise [JobAdapterError] if something goes wrong getting job info
        # @return [Info] information describing submitted job
        # @see Adapter#info
        def info(id)
          id  = id.to_s
          job = @firecrest.get_job(id)
          job ? parse_job_info(job) : Info.new(id: id, status: :completed)
        end

        def parse_job_info(v)
          state  = v.dig("status", "state").to_s
          status = @firecrest.slurm_state_to_ood_state(state)

          connection_info = nil
          begin
            job_name = v["name"].to_s
            # OOD interactive apps set the job name to "<category>/<app>/<category>/<app>"
            # (e.g. "sys/jupyter/sys/jupyter"). This pattern identifies those jobs so we
            # can fetch the connection.yml written by the app at startup.
            if status == :running && /^(?:sys|usr|dev)\/[^\s\/]+\/(?:sys|usr|dev)\/[^\s\/]+$/.match(job_name)
              metadata = @firecrest.get_job_metadata(v["jobId"])
              if metadata && metadata["standardOutput"]
                connect_file = File.join(File.dirname(metadata["standardOutput"]), "connection.yml")
                connection_info = OpenStruct.new(YAML.safe_load(@firecrest.view(connect_file)))
              end
            end
          rescue => e
            Rails.logger.warn("[FirecREST] Failed to read connection info for job #{v["jobId"]}: #{e.message}")
          end

          start_ts = v.dig("time", "start")

          FirecRESTJobInfo.new(
            id:               v["jobId"],
            status:           status,
            allocated_nodes:  parse_nodes(v["nodes"]),
            submit_host:      nil,
            job_name:         v["name"],
            job_owner:        v["user"],
            accounting_id:    v["account"],
            procs:            nil,
            queue_name:       v["partition"],
            wallclock_time:   v.dig("time", "elapsed"),
            wallclock_limit:  v.dig("time", "limit"),
            cpu_time:         nil,
            submission_time:  nil,
            dispatch_time:    start_ts ? Time.at(start_ts) : nil,
            native:           v,
            gpus:             nil,
            ood_connection_info: connection_info
          )
        end

        # Retrieve job status from resource manager.
        # @param id [#to_s] the id of the job
        # @raise [JobAdapterError] if something goes wrong getting job status
        # @return [Status] status of job
        # @see Adapter#status
        def status(id)
          job = @firecrest.get_job(id.to_s)
          if job
            Status.new(state: @firecrest.slurm_state_to_ood_state(job.dig("status", "state").to_s))
          else
            Status.new(state: :undetermined)
          end
        end

        # Put the submitted job on hold.
        # @param id [#to_s] the id of the job
        # @raise [JobAdapterError] if something goes wrong holding a job
        # @return [void]
        # @see Adapter#hold
        def hold(id)
          raise NotImplementedError, "hold not implemented in firecrest adapter yet"
        end

        # Release the job that is on hold.
        # @param id [#to_s] the id of the job
        # @raise [JobAdapterError] if something goes wrong releasing a job
        # @return [void]
        # @see Adapter#release
        def release(id)
          raise NotImplementedError, "release not implemented in firecrest adapter yet"
        end

        # Delete the submitted job.
        # @param id [#to_s] the id of the job
        # @raise [JobAdapterError] if something goes wrong deleting a job
        # @return [void]
        # @see Adapter#delete
        def delete(id)
          @firecrest.delete_job(id.to_s.gsub('.', '_'))
        end

        # Convert host list string to individual node hashes.
        # Handles formats like: "em082", "em[014,055-056]", "c457-[011-012]"
        def parse_nodes(node_list)
          node_list.to_s.scan(/([^,\[]+)(?:\[([^\]]+)\])?/).map do |prefix, range|
            if range
              range.split(",").map do |x|
                if x =~ /^(\d+)-(\d+)$/
                  width = [$1.length, $2.length].max
                  ($1.to_i..$2.to_i).map { |n| n.to_s.rjust(width, '0') }
                else
                  x
                end
              end.flatten.map { |n| { name: prefix + n, procs: nil } }
            elsif prefix
              [ { name: prefix, procs: nil } ]
            else
              []
            end
          end.flatten
        end

      end
    end
  end
end
