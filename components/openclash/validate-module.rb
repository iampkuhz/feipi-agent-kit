# 在路由器使用已安装 OpenClash 的真实合并器，只写指定暂存目录。
require 'yaml'
require '/usr/share/openclash/YAML.rb'
module_file, raw_config, stage = ARGV
raise 'missing stage' unless File.directory?(stage)
body = File.read(module_file)
raise 'wrong scope' unless body.include?('#!CONFIG = oixCloud.yaml')
yaml_block = body.split("[YAML]\n", 2)[1]&.split("[Overwrite]\n", 2)&.first
raise 'missing YAML block' unless yaml_block
File.write("#{stage}/module.yaml", yaml_block)
manifest = "M OIX-Region-Priority.conf\nY #{stage}/module.yaml\n"
(body.split("[Overwrite]\n", 2)[1] || '').lines.each do |line|
  stripped = line.strip
  manifest += "L #{stripped}\n" unless stripped.empty? || stripped.start_with?('#')
end
File.write("#{stage}/manifest", manifest)
File.write("#{stage}/candidate.yaml", File.read(raw_config))
YAML.overwrite_run("#{stage}/candidate.yaml", "#{stage}/manifest")
value = YAML.load_file("#{stage}/candidate.yaml")
groups = value.fetch('proxy-groups')
raise 'duplicate groups' unless groups.map { |g| g['name'] }.uniq.length == groups.length
priority = groups.find { |g| g['name'] == '地区优先' }
raise 'wrong region order' unless priority && priority['proxies'] == %w[香港自动 日本自动 新加坡自动 美国自动 全球自动]
raise 'missing proxy entry' unless groups.find { |g| g['name'] == 'Proxy' }['proxies'].include?('地区优先')
puts 'OVERWRITE_MERGE_OK'
