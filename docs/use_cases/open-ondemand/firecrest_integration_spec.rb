require 'spec_helper'
require 'pathname'
require 'ood_core/job/adapters/firecrest'
require 'ood_core/job/adapters/firecrest/cluster_file'

# Integration tests for the FirecREST v2 adapter.
#
# Requires a real FirecREST installation. Set the following environment variables:
#
#   FIRECREST_CLIENT_ID     - OAuth2 client ID
#   FIRECREST_CLIENT_SECRET - OAuth2 client secret
#   FIRECREST_TOKEN_URI     - Token endpoint URL
#   FIRECREST_URL           - FirecREST base URL (e.g. https://api.cscs.ch/hpc/firecrest/v2)
#   FIRECREST_MACHINE       - Target cluster name (e.g. "daint")
#   FIRECREST_WORK_DIR      - Base directory on the cluster for test files (e.g. /scratch/username)
#   FIRECREST_ACCOUNT       - (optional) Slurm account to use for job submission (-A flag)
#
# Run with:
#   bundle exec rspec spec/job/adapters/firecrest_integration_spec.rb

FIRECREST_REQUIRED_ENV = %w[
  FIRECREST_CLIENT_ID
  FIRECREST_CLIENT_SECRET
  FIRECREST_TOKEN_URI
  FIRECREST_URL
  FIRECREST_MACHINE
  FIRECREST_WORK_DIR
].freeze

def firecrest_env_set?
  FIRECREST_REQUIRED_ENV.all? { |k| ENV[k] && !ENV[k].empty? }
end

RSpec.describe 'FirecREST v2 adapter integration', :order => :defined do
  before(:all) do
    skip "Set #{FIRECREST_REQUIRED_ENV.join(', ')} to run FirecREST integration tests" unless firecrest_env_set?

    batch = OodCore::Job::Adapters::FirecREST::Batch.new(
      machine:  ENV['FIRECREST_MACHINE'],
      endpoint: ENV['FIRECREST_URL']
    )
    @adapter   = OodCore::Job::Adapters::FirecREST.new(firecrest: batch)
    @work_dir  = ENV['FIRECREST_WORK_DIR'].chomp('/')
    @test_dir  = "#{@work_dir}/ood_integration_test_#{Time.now.to_i}"

    puts "\nFirecREST integration tests using machine=#{ENV['FIRECREST_MACHINE']}"
    puts "Test directory on cluster: #{@test_dir}\n"
  end

  # ------------------------------------------------------------------ #
  # Auth / connectivity                                                  #
  # ------------------------------------------------------------------ #

  describe 'connectivity' do
    it 'can obtain an access token and retrieve the current username' do
      username = batch_obj.user
      expect(username).to be_a(String)
      expect(username).not_to be_empty
    end
  end

  # ------------------------------------------------------------------ #
  # File operations                                                      #
  # ------------------------------------------------------------------ #

  describe 'file operations' do
    it 'can create a directory' do
      expect { batch_obj.mkdir(@test_dir, create_intermediate_dirs: true) }.not_to raise_error
    end

    it 'can list files in the created directory' do
      listing = batch_obj.list_files(@test_dir)
      expect(listing).to be_an(Array)
    end

    it 'can upload a file' do
      content = "hello from ood integration test\n"
      expect {
        batch_obj.upload("#{@test_dir}/hello.txt", content: content)
      }.not_to raise_error
    end

    it 'can view an uploaded file' do
      result = batch_obj.view("#{@test_dir}/hello.txt")
      expect(result).to include('hello from ood integration test')
    end

    it 'can list the uploaded file' do
      listing = batch_obj.list_files(@test_dir)
      names = listing.map { |f| f['name'] || f[:name] }
      expect(names).to include('hello.txt')
    end

    it 'can download a file' do
      chunks = []
      batch_obj.download("#{@test_dir}/hello.txt") { |chunk| chunks << chunk }
      expect(chunks.join).to include('hello from ood integration test')
    end

    it 'can delete a file' do
      expect { batch_obj.rm("#{@test_dir}/hello.txt") }.not_to raise_error
    end

    it 'can delete the test directory' do
      expect { batch_obj.rm(@test_dir) }.not_to raise_error
    end
  end

  # ------------------------------------------------------------------ #
  # Job operations                                                       #
  # ------------------------------------------------------------------ #

  describe 'job operations' do
    before(:all) do
      skip "Set #{FIRECREST_REQUIRED_ENV.join(', ')} to run FirecREST integration tests" unless firecrest_env_set?

      @job_name = 'OOD_TEST_' + (0...8).map { (65 + rand(26)).chr }.join
      @script = OodCore::Job::Script.new(
        job_name:      @job_name,
        content:       "#!/bin/bash\nsleep 60\n",
        output_path:   "#{@work_dir}/#{@job_name}.out",
        error_path:    "#{@work_dir}/#{@job_name}.err",
        accounting_id: ENV['FIRECREST_ACCOUNT']
      )
      puts "\nJob name: #{@job_name} (delete manually if tests fail mid-way)\n"
    end

    it 'can submit a job' do
      $firecrest_job_id = @adapter.submit(@script)
      expect($firecrest_job_id).to be_a(String)
      expect($firecrest_job_id).not_to be_empty
      puts "Submitted job id: #{$firecrest_job_id}"
    end

    it 'can get job info by id' do
      info = @adapter.info($firecrest_job_id)
      expect(info).to be_a(OodCore::Job::Info)
      expect(info.id).to eq($firecrest_job_id)
      expect(info.job_name).to eq(@job_name)
    end

    it 'can get job status' do
      status = @adapter.status($firecrest_job_id)
      expect(OodCore::Job::Status.states).to include(status)
      expect([:queued, :queued_held, :running]).to include(status.state)
    end

    it 'can find the job in info_all' do
      jobs = @adapter.info_all
      expect(jobs).to be_an(Array)
      expect(jobs.map(&:id)).to include($firecrest_job_id)
    end

    it 'can find the job via info_where_owner' do
      jobs = @adapter.info_where_owner(batch_obj.user)
      expect(jobs.map(&:id)).to include($firecrest_job_id)
    end

    it 'can delete the job' do
      expect { @adapter.delete($firecrest_job_id) }.not_to raise_error
    end

    it 'job is gone or completed after deletion' do
      sleep 2
      status = @adapter.status($firecrest_job_id)
      expect([:completed, :undetermined]).to include(status.state)
    end
  end

  # ------------------------------------------------------------------ #
  # ClusterFile                                                          #
  # ------------------------------------------------------------------ #

  describe 'ClusterFile' do
    before(:all) do
      skip "Set #{FIRECREST_REQUIRED_ENV.join(', ')} to run FirecREST integration tests" unless firecrest_env_set?

      @cf_dir  = Pathname.new("#{@work_dir}/ood_cf_test_#{Time.now.to_i}")
      @cf_file = @cf_dir.join('hello.txt')

      # Seed: create directory and file via Batch directly
      batch_obj.mkdir(@cf_dir.to_s, create_intermediate_dirs: true)
      batch_obj.upload(@cf_file.to_s, content: "hello cluster file\n")
    end

    after(:all) do
      batch_obj.rm(@cf_dir.to_s) rescue nil if firecrest_env_set?
    end

    it 'directory? returns true for a directory' do
      cf = OodCore::Job::Adapters::FirecREST::ClusterFile.new(@cf_dir, batch_obj)
      expect(cf.directory?).to be true
    end

    it 'directory? returns false for a file' do
      cf = OodCore::Job::Adapters::FirecREST::ClusterFile.new(@cf_file, batch_obj)
      expect(cf.directory?).to be false
    end

    it 'ls lists directory contents' do
      cf = OodCore::Job::Adapters::FirecREST::ClusterFile.new(@cf_dir, batch_obj)
      entries = cf.ls
      expect(entries).to be_an(Array)
      names = entries.map { |e| e[:name] }
      expect(names).to include('hello.txt')
    end

    it 'ls entries have expected keys' do
      cf = OodCore::Job::Adapters::FirecREST::ClusterFile.new(@cf_dir, batch_obj)
      entry = cf.ls.find { |e| e[:name] == 'hello.txt' }
      expect(entry).to include(:id, :name, :size, :human_size, :date, :owner)
    end

    it 'read returns file contents' do
      cf = OodCore::Job::Adapters::FirecREST::ClusterFile.new(@cf_file, batch_obj)
      chunks = []
      cf.read { |chunk| chunks << chunk }
      expect(chunks.join).to include('hello cluster file')
    end

    it 'write updates file contents' do
      cf = OodCore::Job::Adapters::FirecREST::ClusterFile.new(@cf_file, batch_obj)
      cf.write("updated content\n")
      expect(batch_obj.view(@cf_file.to_s)).to include('updated content')
    end

    it 'touch creates an empty file' do
      new_file = OodCore::Job::Adapters::FirecREST::ClusterFile.new(
        @cf_dir.join('touched.txt'), batch_obj
      )
      expect { new_file.touch }.not_to raise_error
    end

    it 'mkdir creates a subdirectory' do
      subdir = OodCore::Job::Adapters::FirecREST::ClusterFile.new(
        @cf_dir.join('subdir'), batch_obj
      )
      expect { subdir.mkdir }.not_to raise_error
    end
  end

  # ------------------------------------------------------------------ #
  # Helpers                                                              #
  # ------------------------------------------------------------------ #

  def batch_obj
    @adapter.instance_variable_get(:@firecrest)
  end
end
