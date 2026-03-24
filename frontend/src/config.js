const config = {
    // Dynamically set API BASE URL based on the current hostname to handle both localhost and IP access
    API_BASE_URL: `${window.location.protocol}//${window.location.hostname}:8000`,
};

export default config;
