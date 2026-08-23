# Next.js Google Login Integration Guide

This guide provides a production-ready, step-by-step implementation for integrating the Django `django-allauth` Google Social Login API in a **Next.js (App Router + TypeScript + TanStack Query)** application.

---

## 1. Installation

Install `@react-oauth/google`, `@tanstack/react-query`, and `axios`:

```bash
npm install @react-oauth/google @tanstack/react-query axios
```

---

## 2. Environment Setup

Create or update `.env.local`:

```env
NEXT_PUBLIC_GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api
```

---

## 3. TypeScript Interfaces

`types/auth.ts`

```typescript
export interface UserProfile {
  id: number;
  username: string;
  email: string;
  role: string;
  branch: number | null;
}

export interface AuthTokens {
  access: string;
  refresh: string;
}

export interface GoogleLoginRequest {
  id_token?: string;
  access_token?: string;
  client_id?: string;
}

export interface AuthResponse {
  message: string;
  tokens: AuthTokens;
  user: UserProfile;
}
```

---

## 4. API Client Layer

`api/auth.ts`

```typescript
import axios from 'axios';
import { GoogleLoginRequest, AuthResponse } from '@/types/auth';

const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

export const loginWithGoogle = async (payload: GoogleLoginRequest): Promise<AuthResponse> => {
  const response = await apiClient.post<AuthResponse>('/auth/social/google/', payload);
  return response.data;
};
```

---

## 5. TanStack Query Mutation Hook

`hooks/useGoogleLogin.ts`

```typescript
import { useMutation } from '@tanstack/react-query';
import { loginWithGoogle } from '@/api/auth';
import { GoogleLoginRequest, AuthResponse } from '@/types/auth';

export const useGoogleLoginMutation = () => {
  return useMutation<AuthResponse, Error, GoogleLoginRequest>({
    mutationFn: (payload) => loginWithGoogle(payload),
    onSuccess: (data) => {
      // Store tokens securely (e.g., localStorage, cookies)
      localStorage.setItem('access_token', data.tokens.access);
      localStorage.setItem('refresh_token', data.tokens.refresh);
      localStorage.setItem('user_profile', JSON.stringify(data.user));
    },
  });
};
```

---

## 6. Google Provider & Login Button Component

`components/GoogleLoginButton.tsx`

```tsx
'use client';

import React from 'react';
import { GoogleOAuthProvider, GoogleLogin, CredentialResponse } from '@react-oauth/google';
import { useGoogleLoginMutation } from '@/hooks/useGoogleLogin';

interface GoogleLoginButtonProps {
  onSuccessCallback?: () => void;
  onErrorCallback?: (error: string) => void;
}

export const GoogleLoginButton: React.FC<GoogleLoginButtonProps> = ({
  onSuccessCallback,
  onErrorCallback,
}) => {
  const clientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || '';
  const { mutate: performGoogleLogin, isPending, isError, error } = useGoogleLoginMutation();

  const handleSuccess = (credentialResponse: CredentialResponse) => {
    if (!credentialResponse.credential) {
      onErrorCallback?.('Google ID token was not returned.');
      return;
    }

    performGoogleLogin(
      { id_token: credentialResponse.credential },
      {
        onSuccess: () => {
          if (onSuccessCallback) onSuccessCallback();
        },
        onError: (err) => {
          if (onErrorCallback) onErrorCallback(err.message);
        },
      }
    );
  };

  if (!clientId) {
    return <p className="text-red-500 text-sm">Google Client ID is missing in environment variables.</p>;
  }

  return (
    <GoogleOAuthProvider clientId={clientId}>
      <div className="flex flex-col items-center gap-3">
        <GoogleLogin
          onSuccess={handleSuccess}
          onError={() => onErrorCallback?.('Google Login Failed')}
          useOneTap
          theme="outline"
          shape="rectangular"
        />

        {isPending && <p className="text-sm text-gray-500">Authenticating with backend...</p>}
        {isError && <p className="text-sm text-red-500">{error.message}</p>}
      </div>
    </GoogleOAuthProvider>
  );
};
```

---

## 7. Example Next.js Login Page Usage

`app/login/page.tsx`

```tsx
'use client';

import React from 'react';
import { useRouter } from 'next/navigation';
import { GoogleLoginButton } from '@/components/GoogleLoginButton';

export default function LoginPage() {
  const router = useRouter();

  const handleLoginSuccess = () => {
    // Redirect to dashboard or home page after successful login
    router.push('/dashboard');
  };

  const handleLoginError = (errorMessage: string) => {
    console.error('Login error:', errorMessage);
  };

  return (
    <main className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="bg-white p-8 rounded-xl shadow-md w-full max-w-md text-center">
        <h1 className="text-2xl font-bold mb-6 text-gray-800">Sign In</h1>
        <div className="my-4">
          <GoogleLoginButton
            onSuccessCallback={handleLoginSuccess}
            onErrorCallback={handleLoginError}
          />
        </div>
      </div>
    </main>
  );
}
```
