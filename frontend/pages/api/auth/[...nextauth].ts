import NextAuth, { NextAuthOptions } from 'next-auth';
import CredentialsProvider from 'next-auth/providers/credentials';

export const authOptions: NextAuthOptions = {
  providers: [
    CredentialsProvider({
      name: 'Credentials',
      credentials: {
        username: { label: 'Username', type: 'text' },
        password: { label: 'Password', type: 'password' },
      },
      async authorize(credentials) {
        const u = process.env.AUTH_USERNAME || 'admin';
        const p = process.env.AUTH_PASSWORD || 'admin';
        if (credentials?.username === u && credentials?.password === p) {
          return { id: '1', name: u } as any;
        }
        return null;
      },
    }),
  ],
  pages: {
    signIn: '/auth/signin',
  },
  session: { strategy: 'jwt' },
  secret: process.env.NEXTAUTH_SECRET || 'please_set_nextauth_secret',
};

export default NextAuth(authOptions); 