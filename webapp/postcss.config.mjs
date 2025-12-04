const config = {
  plugins: {
    "@tailwindcss/postcss": {},
    "postcss-preset-env": {
      features: {
        "oklab-function": true,
      },
    },
  },
};

export default config;
