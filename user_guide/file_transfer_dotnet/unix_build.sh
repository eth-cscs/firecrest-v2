#!/bin/bash
# Unix patch and build script
sed -i '/<Exec Command="copy $(SolutionDir)\\\.credentials_demo $(TargetDir)\\\.credentials" \/>/d' firecrest_base/firecrest_base.csproj
sed -i '/<Exec Command="copy $(SolutionDir)\\\.credentials_demo $(TargetDir)\\\.credentials" \/>/d' large_files_transfer/large_files_transfer.csproj
sed -i '/<Exec Command="copy $(SolutionDir)\\\.credentials_demo $(TargetDir)\\\.credentials" \/>/d' small_files_transfer/small_files_transfer.csproj
dotnet build --output examples_bin
cp .credentials_demo examples_bin/.credentials
