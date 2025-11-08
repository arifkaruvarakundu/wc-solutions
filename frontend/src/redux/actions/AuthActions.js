import api from "../../../api_config"; // adjust path based on your folder structure

export const login = (email, password) => async dispatch => {
  try {
    dispatch({ type: "AUTH_REQUEST" });

    const { data } = await api.post("/login", { email, password });

    console.log("user_type", data)
    
    // Save token in localStorage
    localStorage.setItem("token", data.access_token);
    localStorage.setItem("email", data.email);
    // localStorage.setItem("user_type", data.user_type);
    
    dispatch({
      type: "AUTH_SUCCESS",
      payload: { token: data.access_token, email: data.email },
    });
  } catch (error) {
    dispatch({
      type: "AUTH_FAIL",
      payload: error.response?.data?.detail || "Login failed",
    });
  }
};

export const register =
  (email, password, client_name, store_url, consumer_key, consumer_secret) =>
  async (dispatch) => {
    try {
      dispatch({ type: "AUTH_REQUEST" });

      const { data } = await api.post("/register", {
        email,
        password,
        client_name,
        store_url,
        consumer_key,
        consumer_secret,
      });

      localStorage.setItem("token", data.access_token);
      localStorage.setItem("email", data.email);

      dispatch({
        type: "AUTH_SUCCESS",
        payload: { token: data.access_token, email: data.email },
      });

      // ✅ Return full backend response to frontend
      return { payload: data };
    } catch (error) {
      let message = "Registration failed";
      const detail = error.response?.data?.detail;

      if (Array.isArray(detail)) {
        message = detail.map((err) => err.msg).join(", ");
      } else if (typeof detail === "string") {
        message = detail;
      }

      dispatch({
        type: "AUTH_FAIL",
        payload: message,
      });

      throw new Error(message); // ✅ also propagate to frontend catch
    }
  };

  export const logout = () => async (dispatch) => {
    try {
      // Call the backend logout endpoint
      await api.post("/logout");
  
      // Clear localStorage after successful logout
      localStorage.clear();
  
      dispatch({ type: "LOGOUT" });
    } catch (error) {
      console.error("Logout failed:", error.response?.data || error.message);
  
      // Still clear localStorage to ensure client-side logout
      localStorage.clear();
      dispatch({ type: "LOGOUT" });
    }
  };
