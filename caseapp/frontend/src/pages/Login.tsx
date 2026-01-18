import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { signIn, setUpTOTP, confirmSignIn } from 'aws-amplify/auth';
import { motion, AnimatePresence } from 'framer-motion';
import { Shield, Lock, Mail, ArrowRight, Loader2, AlertCircle, Scale, QrCode, RefreshCw } from 'lucide-react';
import { QRCodeCanvas } from 'qrcode.react';
import { useAuth } from '../contexts/AuthContext';

const Login: React.FC = () => {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    
    // MFA Setup State
    const [mfaSetup, setMfaSetup] = useState(false);
    const [mfaCodeRequired, setMfaCodeRequired] = useState(false);
    const [totpSecretCode, setTotpSecretCode] = useState<string>('');
    const [qrCodeUrl, setQrCodeUrl] = useState<string>('');
    const [verificationCode, setVerificationCode] = useState('');
    const [isSetupLoading, setIsSetupLoading] = useState(false);

    const navigate = useNavigate();
    const location = useLocation();
    const { checkUser } = useAuth();

    const from = location.state?.from?.pathname || '/';

    const initiateTOTPSetup = async (details?: any) => {
        setIsSetupLoading(true);
        setError(null);
        try {
            console.log('Initiating TOTP Setup...', details ? 'Using provided details' : 'Fetching new details');
            const totpSetupDetails = details || await setUpTOTP();
            
            console.log('TOTP Details processed');
            setTotpSecretCode(totpSetupDetails.sharedSecret);
            const appName = "Antigravity Case System";
            // Use getSetupUri if available, otherwise construct manually
            const setupUrl = totpSetupDetails.getSetupUri 
                ? totpSetupDetails.getSetupUri(appName) 
                : `otpauth://totp/${encodeURIComponent(appName)}:${encodeURIComponent(email)}?secret=${totpSetupDetails.sharedSecret}&issuer=${encodeURIComponent(appName)}`;
            
            setQrCodeUrl(setupUrl);
        } catch (err: any) {
            console.error('TOTP Setup failed:', err);
            setError(`Failed to initiate 2FA setup: ${err.message || 'Unknown error'}`);
        } finally {
            setIsSetupLoading(false);
        }
    };

    const handleVerifyTOTP = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsLoading(true);
        setError(null);
        try {
            // verifyTOTPSetup is for authenticated users enabling MFA. 
            // For login flow, confirmSignIn handles the verification.
            await confirmSignIn({ challengeResponse: verificationCode });
            await checkUser();
            navigate(from, { replace: true });
        } catch (err: any) {
            console.error('TOTP Verification failed:', err);
            setError(err.message || 'Invalid code. Please try again.');
        } finally {
            setIsLoading(false);
        }
    };

    const [newPassword, setNewPassword] = useState('');
    const [newPasswordRequired, setNewPasswordRequired] = useState(false);

    const handleNewPasswordSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsLoading(true);
        setError(null);
        try {
            const { isSignedIn, nextStep } = await confirmSignIn({ challengeResponse: newPassword });
            if (isSignedIn) {
                await checkUser();
                navigate(from, { replace: true });
            } else {
                 if (nextStep.signInStep === 'CONTINUE_SIGN_IN_WITH_TOTP_SETUP') {
                    setMfaSetup(true);
                    setNewPasswordRequired(false);
                    await initiateTOTPSetup(nextStep.totpSetupDetails);
                } else {
                    setError(`Unexpected next step: ${nextStep.signInStep}`);
                }
            }
        } catch (err: any) {
            console.error('New Password error:', err);
            setError(err.message || 'Failed to set new password');
        } finally {
            setIsLoading(false);
        }
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsLoading(true);
        setError(null);

        try {
            const { isSignedIn, nextStep } = await signIn({ username: email, password });

            if (isSignedIn) {
                await checkUser();
                navigate(from, { replace: true });
            } else {
                console.log('Next step:', nextStep);
                if (nextStep.signInStep === 'CONTINUE_SIGN_IN_WITH_TOTP_SETUP') {
                    setMfaSetup(true);
                    await initiateTOTPSetup(nextStep.totpSetupDetails);
                } else if (nextStep.signInStep === 'CONFIRM_SIGN_IN_WITH_NEW_PASSWORD_REQUIRED') {
                    setNewPasswordRequired(true);
                } else if (nextStep.signInStep === 'CONFIRM_SIGN_IN_WITH_TOTP_CODE') {
                    setMfaCodeRequired(true);
                } else if (nextStep.signInStep === 'CONFIRM_SIGN_UP') {
                    setError('Account not confirmed. Please check your email.');
                } else {
                    setError(`Additional authentication step required: ${nextStep.signInStep}`);
                }
            }
        } catch (err: any) {
            console.error('Login error:', err);
            setError(err.message || 'An error occurred during login');
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-[#0f172a] flex items-center justify-center p-4 relative overflow-hidden">
            {/* Background Blobs */}
            <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-blue-600/10 rounded-full blur-[120px] animate-pulse" />
            <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-indigo-600/10 rounded-full blur-[120px] animate-pulse" style={{ animationDelay: '2s' }} />

            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="w-full max-w-md"
            >
                <div className="mb-8 text-center italic">
                    <motion.div
                        initial={{ scale: 0.8 }}
                        animate={{ scale: 1 }}
                        className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500 to-indigo-600 shadow-lg shadow-blue-500/20 mb-4"
                    >
                        <Scale className="w-8 h-8 text-white" />
                    </motion.div>
                    <h1 className="text-3xl font-bold text-white tracking-tight">Antigravity</h1>
                    <p className="text-slate-400 mt-2">Law Case Management System</p>
                </div>

                <div className="bg-slate-900/50 backdrop-blur-xl border border-slate-800 rounded-3xl p-8 shadow-2xl relative overflow-hidden">
                    <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-blue-500 to-transparent opacity-50" />

                    <AnimatePresence mode="wait">
                        {mfaSetup || mfaCodeRequired ? (
                            <motion.form key="mfa-form" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} onSubmit={handleVerifyTOTP} className="space-y-6">
                                {mfaSetup && (
                                    <>
                                        <div className="flex flex-col items-center justify-center p-6 bg-white rounded-xl shadow-inner min-h-[220px]">
                                            {isSetupLoading ? (
                                                <div className="flex flex-col items-center gap-2 text-slate-400">
                                                    <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
                                                    <span className="text-sm">Generating Security Key...</span>
                                                </div>
                                            ) : qrCodeUrl ? (
                                                <div className="p-2 bg-white rounded-lg">
                                                    <QRCodeCanvas 
                                                        value={qrCodeUrl} 
                                                        size={300}
                                                        level={"H"}
                                                        includeMargin={true}
                                                        style={{ width: '300px', height: '300px', maxWidth: '100%' }}
                                                    />
                                                </div>
                                            ) : (
                                                <div className="flex flex-col items-center gap-2">
                                                    <p className="text-slate-900 text-sm mb-2 text-center text-red-500">Failed to load QR Code</p>
                                                    <button 
                                                        type="button" 
                                                        onClick={() => initiateTOTPSetup()}
                                                        className="flex items-center gap-2 text-xs bg-slate-100 hover:bg-slate-200 text-slate-700 px-3 py-2 rounded-lg transition-colors"
                                                    >
                                                        <RefreshCw className="w-3 h-3" /> Retry Generation
                                                    </button>
                                                </div>
                                            )}
                                        </div>
                                        
                                        <div className="text-center text-sm text-slate-400">
                                            <p className="mb-2">Scan with Google Authenticator or Authy</p>
                                            {totpSecretCode && (
                                                <div className="flex flex-col items-center gap-1">
                                                    <span className="text-xs text-slate-500">Manual Entry Code:</span>
                                                    <p className="font-mono text-xs text-blue-400 bg-blue-400/10 px-2 py-1 rounded cursor-pointer hover:bg-blue-400/20 active:scale-95 transition-all select-all" 
                                                    onClick={() => navigator.clipboard.writeText(totpSecretCode)}
                                                    title="Click to copy"
                                                    >
                                                        {totpSecretCode}
                                                    </p>
                                                </div>
                                            )}
                                        </div>
                                    </>
                                )}
                                
                                <div className="space-y-2 text-center">
                                    <label className="text-sm font-medium text-slate-400 ml-1">
                                        {mfaSetup ? 'Enter Verification Code' : 'Enter 6-digit Security Code'}
                                    </label>
                                    <div className="relative group">
                                        <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-slate-500 group-focus-within:text-blue-500 transition-colors">
                                            <QrCode className="w-5 h-5" />
                                        </div>
                                        <input
                                            type="text"
                                            value={verificationCode}
                                            onChange={(e) => setVerificationCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                                            className="w-full bg-slate-950/50 border border-slate-800 focus:border-blue-500/50 focus:ring-4 focus:ring-blue-500/10 rounded-xl py-3 pl-12 pr-4 text-white placeholder-slate-600 outline-none transition-all tracking-widest font-mono text-center text-lg"
                                            placeholder="000000"
                                            required
                                            maxLength={6}
                                        />
                                    </div>
                                </div>

                                {error && (
                                    <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-3 flex items-start gap-3 text-red-400 text-sm">
                                        <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
                                        <div className="flex-1">
                                            <p>{error}</p>
                                            {error.includes('initiate') && (
                                                <button 
                                                    type="button" 
                                                    onClick={initiateTOTPSetup}
                                                    className="mt-2 text-xs text-red-300 hover:text-white underline underline-offset-2"
                                                >
                                                    Try Again
                                                </button>
                                            )}
                                        </div>
                                    </div>
                                )}

                                <button
                                    type="submit"
                                    disabled={isLoading || verificationCode.length !== 6}
                                    className="w-full bg-blue-600 hover:bg-blue-500 disabled:bg-blue-600/50 text-white font-semibold py-3.5 rounded-xl shadow-lg shadow-blue-600/20 flex items-center justify-center gap-2 group transition-all"
                                >
                                    {isLoading ? (
                                        <Loader2 className="w-5 h-5 animate-spin" />
                                    ) : (
                                        <>
                                            {mfaSetup ? 'Verify & Enable 2FA' : 'Complete Sign In'}
                                            <Shield className="w-5 h-5 group-hover:scale-110 transition-transform" />
                                        </>
                                    )}
                                </button>
                            </motion.form>
                        ) : newPasswordRequired ? (
                            <motion.form key="new-password-form" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} onSubmit={handleNewPasswordSubmit} className="space-y-6">
                                <div className="space-y-2">
                                    <label className="text-sm font-medium text-slate-400 ml-1">New Password</label>
                                    <div className="relative group">
                                        <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-slate-500 group-focus-within:text-blue-500 transition-colors">
                                            <Lock className="w-5 h-5" />
                                        </div>
                                        <input
                                            type="password"
                                            value={newPassword}
                                            onChange={(e) => setNewPassword(e.target.value)}
                                            className="w-full bg-slate-950/50 border border-slate-800 focus:border-blue-500/50 focus:ring-4 focus:ring-blue-500/10 rounded-xl py-3 pl-12 pr-4 text-white placeholder-slate-600 outline-none transition-all"
                                            placeholder="Set new password"
                                            required
                                            minLength={8}
                                        />
                                    </div>
                                    <p className="text-xs text-slate-500 ml-1">Must be at least 8 characters</p>
                                </div>

                                {error && (
                                    <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-3 flex items-start gap-3 text-red-400 text-sm">
                                        <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
                                        <p>{error}</p>
                                    </div>
                                )}

                                <button
                                    type="submit"
                                    disabled={isLoading}
                                    className="w-full bg-blue-600 hover:bg-blue-500 disabled:bg-blue-600/50 text-white font-semibold py-3.5 rounded-xl shadow-lg shadow-blue-600/20 flex items-center justify-center gap-2 group transition-all"
                                >
                                    {isLoading ? (
                                        <Loader2 className="w-5 h-5 animate-spin" />
                                    ) : (
                                        <>
                                            Set Password & Continue
                                            <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                                        </>
                                    )}
                                </button>
                            </motion.form>
                        ) : (
                            <motion.form key="login-form" initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} onSubmit={handleSubmit} className="space-y-5">
                                <div className="space-y-2">
                                    <label className="text-sm font-medium text-slate-400 ml-1">Email Address</label>
                                    <div className="relative group">
                                        <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-slate-500 group-focus-within:text-blue-500 transition-colors">
                                            <Mail className="w-5 h-5" />
                                        </div>
                                        <input
                                            type="email"
                                            value={email}
                                            onChange={(e) => setEmail(e.target.value)}
                                            className="w-full bg-slate-950/50 border border-slate-800 focus:border-blue-500/50 focus:ring-4 focus:ring-blue-500/10 rounded-xl py-3 pl-12 pr-4 text-white placeholder-slate-600 outline-none transition-all"
                                            placeholder="name@agency.gov"
                                            required
                                        />
                                    </div>
                                </div>

                                <div className="space-y-2">
                                    <div className="flex items-center justify-between ml-1">
                                        <label className="text-sm font-medium text-slate-400">Password</label>
                                        <button type="button" className="text-xs text-blue-500 hover:text-blue-400 transition-colors">Forgot password?</button>
                                    </div>
                                    <div className="relative group">
                                        <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-slate-500 group-focus-within:text-blue-500 transition-colors">
                                            <Lock className="w-5 h-5" />
                                        </div>
                                        <input
                                            type="password"
                                            value={password}
                                            onChange={(e) => setPassword(e.target.value)}
                                            className="w-full bg-slate-950/50 border border-slate-800 focus:border-blue-500/50 focus:ring-4 focus:ring-blue-500/10 rounded-xl py-3 pl-12 pr-4 text-white placeholder-slate-600 outline-none transition-all"
                                            placeholder="••••••••••••"
                                            required
                                        />
                                    </div>
                                </div>

                                <AnimatePresence mode="wait">
                                    {error && (
                                        <motion.div
                                            initial={{ opacity: 0, height: 0 }}
                                            animate={{ opacity: 1, height: 'auto' }}
                                            exit={{ opacity: 0, height: 0 }}
                                            className="bg-red-500/10 border border-red-500/20 rounded-xl p-3 flex items-start gap-3 text-red-400 text-sm"
                                        >
                                            <AlertCircle className="w-5 h-5 shrink-0" />
                                            <p>{error}</p>
                                        </motion.div>
                                    )}
                                </AnimatePresence>

                                <button
                                    type="submit"
                                    disabled={isLoading}
                                    className="w-full bg-blue-600 hover:bg-blue-500 disabled:bg-blue-600/50 text-white font-semibold py-3.5 rounded-xl shadow-lg shadow-blue-600/20 flex items-center justify-center gap-2 group transition-all"
                                >
                                    {isLoading ? (
                                        <Loader2 className="w-5 h-5 animate-spin" />
                                    ) : (
                                        <>
                                            Secure Sign In
                                            <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                                        </>
                                    )}
                                </button>
                            </motion.form>
                        )}
                    </AnimatePresence>

                    <div className="mt-8 pt-6 border-t border-slate-800 flex items-center justify-center gap-2 text-slate-500 text-sm">
                        <Shield className="w-4 h-4" />
                        <span>Authorized Personnel Only</span>
                    </div>
                </div>

                <p className="text-center text-slate-500 text-xs mt-8 uppercase tracking-widest font-medium">
                    Federal Intelligence Network • Protected System
                </p>
            </motion.div>
        </div>
    );
};

export default Login;
