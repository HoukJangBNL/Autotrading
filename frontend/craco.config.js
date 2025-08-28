module.exports = {
  webpack: {
    configure: (webpackConfig) => {
      // Disable ForkTsCheckerWebpackPlugin
      const ForkTsCheckerWebpackPlugin = webpackConfig.plugins.find(
        (plugin) => plugin.constructor.name === 'ForkTsCheckerWebpackPlugin'
      );
      
      if (ForkTsCheckerWebpackPlugin) {
        // Increase memory limit for the TypeScript checker
        ForkTsCheckerWebpackPlugin.memoryLimit = 4096;
        // Or completely disable it for now
        webpackConfig.plugins = webpackConfig.plugins.filter(
          (plugin) => plugin.constructor.name !== 'ForkTsCheckerWebpackPlugin'
        );
      }
      
      return webpackConfig;
    },
  },
};