import React, { useState, useEffect, useRef } from "react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { ShoppingBag, Lock, Eye, EyeOff } from "lucide-react";
import { useDispatch } from "react-redux";
import { register } from "../redux/actions/AuthActions";
import { useNavigate } from "react-router-dom";
import api from "../../api_config";

export default function RegisterPage() {
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [showAdvanced] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState("");
  const [form, setForm] = useState({
    email: "",
    password: "",
    confirmPassword: "",
    client_name: "",
    store_url: "",
    consumer_key: "",
    consumer_secret: "",
  });

  const dispatch = useDispatch();
  const navigate = useNavigate();

  // refs to hold interval IDs so we can clear them reliably
  const taskIntervalRef = useRef(null);
  const syncIntervalRef = useRef(null);
  // ref to avoid starting multiple task polls
  const isTaskPollingRef = useRef(false);

  const handleChange = (e) => {
    setForm((prev) => ({
      ...prev,
      [e.target.name]: e.target.value,
    }));
  };

  const startTaskPolling = (taskId) => {
    if (!taskId) return;
    if (isTaskPollingRef.current) return; // already polling
    isTaskPollingRef.current = true;

    let attempts = 0;
    const maxAttempts = 60; // 5 minutes at 5s

    taskIntervalRef.current = setInterval(async () => {
      try {
        attempts += 1;
        const statusRes = await api.get(`/task-status/${taskId}`);
        const statusData = statusRes?.data;

        console.log("Task status:", statusData);

        if (statusData?.status === "SUCCESS") {
          clearInterval(taskIntervalRef.current);
          taskIntervalRef.current = null;
          isTaskPollingRef.current = false;

          setSyncMessage("✅ Store synced successfully!");
          // small delay so user sees success then navigate
          setTimeout(() => {
            setIsSyncing(false);
            navigate("/dashboard");
          }, 1200);
        } else if (statusData?.status === "FAILURE") {
          clearInterval(taskIntervalRef.current);
          taskIntervalRef.current = null;
          isTaskPollingRef.current = false;
          setIsSyncing(false);
          alert("❌ Sync failed, please try again later.");
        } else if (attempts >= maxAttempts) {
          clearInterval(taskIntervalRef.current);
          taskIntervalRef.current = null;
          isTaskPollingRef.current = false;
          setIsSyncing(false);
          alert("⏳ Sync taking too long, check again later.");
        } else {
          // optionally update message with status
          setSyncMessage("Setting up your store and fetching WooCommerce data...");
        }
      } catch (pollError) {
        console.error("Polling error:", pollError);
        clearInterval(taskIntervalRef.current);
        taskIntervalRef.current = null;
        isTaskPollingRef.current = false;
        setIsSyncing(false);
      }
    }, 5000);
  };

  useEffect(() => {
    let interval;
  
    const checkSyncStatus = async () => {
      const email = localStorage.getItem("email");
      if (!email) return;
  
      try {
        const { data } = await api.get(`/sync-status/${email}`);
  
        if (data?.sync_status === "COMPLETE") {
          setSyncMessage("✅ Store synced successfully!");
          setTimeout(() => {
            setIsSyncing(false);
            navigate("/dashboard");
          }, 1000);
        } else if (data?.sync_status === "IN_PROGRESS" || data?.sync_status === "PENDING") {
          setIsSyncing(true);
          setSyncMessage("🔄 Syncing your store data...");
        } else if (data?.sync_status === "FAILED") {
          setIsSyncing(false);
          alert("❌ Sync failed, please try again later.");
        }
      } catch (err) {
        console.error("Failed to check sync status:", err);
      }
    };
  
    // run immediately and then every 5 seconds
    checkSyncStatus();
    interval = setInterval(checkSyncStatus, 5000);
  
    return () => clearInterval(interval);
  }, [navigate]);

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (form.password !== form.confirmPassword) {
      alert("Passwords do not match");
      return;
    }

    try {
      // Dispatch Redux register action
      const res = await dispatch(
        register(
          form.email,
          form.password,
          form.client_name,
          form.store_url,
          form.consumer_key,
          form.consumer_secret
        )
      );

      const data = res?.payload || {};
      if (!data || !data.client_id) {
        throw new Error("Registration failed — no client data returned");
      }

      // Save email/token for background checks (dashboard or refresh)
      // if (data.access_token) localStorage.setItem("token", data.access_token);
      // if (data.email) localStorage.setItem("email", data.email);

      // Show syncing overlay
      setIsSyncing(true);
      setSyncMessage("Setting up your store and fetching WooCommerce data...");

    } catch (err) {
      console.error(err);
      alert(err.message || "Registration failed");
      setIsSyncing(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-[oklch(0.98_0.01_265)] via-background to-[oklch(0.96_0.02_240)] flex items-center justify-center p-4">
      <div className="w-full max-w-2xl">
        {/* Header */}
        <div className="text-center mb-8">
          <a href="/" className="inline-flex items-center gap-2 mb-6 group">
            <div className="w-10 h-10 rounded-xl bg-primary flex items-center justify-center">
              <ShoppingBag className="w-6 h-6 text-primary-foreground" />
            </div>
            <span className="text-xl font-bold text-foreground">WooAnalytics</span>
          </a>
          <h1 className="text-4xl font-bold text-foreground mb-3 text-balance">
            Start Analyzing Your Store
          </h1>
          <p className="text-muted-foreground text-lg">
            Create your account and unlock powerful insights
          </p>
        </div>

        {/* Registration Form */}
        <Card className="border-border/50 shadow-2xl">
          <CardHeader>
            <CardTitle className="text-2xl">Create Account</CardTitle>
            <CardDescription>
              Enter your details to get started with WooCommerce analytics
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-6">
              {/* Basic Information */}
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="email">Email Address *</Label>
                  <Input
                    id="email"
                    name="email"
                    type="email"
                    placeholder="you@company.com"
                    required
                    value={form.email}
                    onChange={handleChange}
                    className="h-11"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="password">Password *</Label>
                  <div className="relative">
                    <Input
                      id="password"
                      name="password"
                      type={showPassword ? "text" : "password"}
                      placeholder="Create a strong password"
                      required
                      value={form.password}
                      onChange={handleChange}
                      className="h-11 pr-10"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                    >
                      {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="confirmPassword">Confirm Password *</Label>
                  <div className="relative">
                    <Input
                      id="confirmPassword"
                      name="confirmPassword"
                      type={showConfirmPassword ? "text" : "password"}
                      placeholder="Confirm password"
                      required
                      value={form.confirmPassword}
                      onChange={handleChange}
                      className="h-11 pr-10"
                    />
                    <button
                      type="button"
                      onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                    >
                      {showConfirmPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="client_name">Full Name</Label>
                  <Input
                    id="client_name"
                    name="client_name"
                    type="text"
                    placeholder="John Doe"
                    value={form.client_name}
                    onChange={handleChange}
                    className="h-11"
                  />
                </div>
              </div>

              {/* WooCommerce Credentials Section */}
              <div className="border-t border-border pt-6">
                <div className="flex items-center gap-2">
                  <Lock className="w-4 h-4 text-primary" />
                  <span className="font-semibold text-foreground">WooCommerce Credentials</span>
                </div>

                {showAdvanced && (
                  <div className="space-y-4 animate-in fade-in slide-in-from-top-2 duration-300">
                    <p className="text-sm text-muted-foreground mb-4">Add your WooCommerce store details</p>

                    <div className="space-y-2">
                      <Label htmlFor="store_url">Store URL</Label>
                      <Input
                        id="store_url"
                        name="store_url"
                        type="url"
                        placeholder="https://yourstore.com"
                        value={form.store_url}
                        onChange={handleChange}
                        className="h-11"
                      />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="consumer_key">Consumer Key</Label>
                      <Input
                        id="consumer_key"
                        name="consumer_key"
                        type="text"
                        placeholder="ck_xxxxxxxxxxxxxxxx"
                        value={form.consumer_key}
                        onChange={handleChange}
                        className="h-11 font-mono text-sm"
                      />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="consumer_secret">Consumer Secret</Label>
                      <Input
                        id="consumer_secret"
                        name="consumer_secret"
                        type="password"
                        placeholder="cs_xxxxxxxxxxxxxxxx"
                        value={form.consumer_secret}
                        onChange={handleChange}
                        className="h-11 font-mono text-sm"
                      />
                    </div>

                    <div className="bg-muted/50 border border-border rounded-lg p-4">
                      <p className="text-sm text-muted-foreground">
                        <Lock className="w-4 h-4 inline mr-1" />
                        Your credentials are encrypted and stored securely
                      </p>
                    </div>
                  </div>
                )}
              </div>

              {/* Submit Button */}
              <Button type="submit" className="w-full h-12 text-base font-semibold" size="lg">
                Create Account
              </Button>

              {/* Terms */}
              <p className="text-sm text-muted-foreground text-center">
                By creating an account, you agree to our{" "}
                <a href="/terms" className="text-primary hover:underline">Terms of Service</a> and{" "}
                <a href="/privacy" className="text-primary hover:underline">Privacy Policy</a>
              </p>
            </form>
          </CardContent>
        </Card>

        {/* Sign In Link */}
        <p className="text-center mt-6 text-muted-foreground">
          Already have an account? <a href="/login" className="text-primary font-semibold hover:underline">Sign in</a>
        </p>
      </div>

      {/* ✅ Syncing Overlay */}
      {isSyncing && (
        <div className="fixed inset-0 bg-background/80 backdrop-blur-sm flex flex-col items-center justify-center z-50">
          <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary border-t-transparent mb-4"></div>
          <h2 className="text-lg font-semibold mb-2">{syncMessage || "Syncing your store..."}</h2>
          <p className="text-sm text-muted-foreground">This may take a few minutes...</p>
        </div>
      )}
    </div>
  );
}
