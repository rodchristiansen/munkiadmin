platform :osx, '10.13'

target 'MunkiAdmin' do
pod 'NSHash', '~> 1.0.1'
pod 'CocoaLumberjack'
pod 'CHCSVParser', :git => 'https://github.com/davedelong/CHCSVParser.git'
pod 'YAMLFrameworkOrdered', '~> 0.0.2'
end

post_install do |installer|
  installer.pods_project.targets.each do |target|
    if target.name == 'LibYAML'
      target.build_configurations.each do |config|
        config.build_settings['GCC_PREPROCESSOR_DEFINITIONS'] ||= ['$(inherited)']
        config.build_settings['GCC_PREPROCESSOR_DEFINITIONS'] << 'HAVE_CONFIG_H=1'
        config.build_settings['HEADER_SEARCH_PATHS'] ||= ['$(inherited)']
        config.build_settings['HEADER_SEARCH_PATHS'] << '"$(PODS_ROOT)/LibYAML"'
      end
    end
  end
end
