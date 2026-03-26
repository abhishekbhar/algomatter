"use client";
import {
  Box,
  Button,
  FormControl,
  FormLabel,
  Input,
  VStack,
  Heading,
  Text,
  Link as ChakraLink,
  useToast,
  FormErrorMessage,
} from "@chakra-ui/react";
import NextLink from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useAuth } from "@/lib/hooks/useAuth";
import { ApiError } from "@/lib/api/client";

export default function SignupPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { signup } = useAuth();
  const router = useRouter();
  const toast = useToast();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }
    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    setIsSubmitting(true);
    try {
      await signup(email, password);
      router.push("/");
    } catch (err) {
      if (err instanceof ApiError) setError("Signup failed. Email may already be in use.");
      else toast({ title: "Network error", status: "error" });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Box maxW="400px" mx="auto" mt={20} p={8}>
      <Heading size="lg" mb={6}>
        Sign Up
      </Heading>
      <form onSubmit={handleSubmit}>
        <VStack spacing={4}>
          <FormControl isRequired isInvalid={!!error && error.includes("Email")}>
            <FormLabel htmlFor="email">Email</FormLabel>
            <Input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </FormControl>
          <FormControl isRequired isInvalid={!!error && error.includes("Password")}>
            <FormLabel htmlFor="password">Password</FormLabel>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </FormControl>
          <FormControl isRequired isInvalid={!!error}>
            <FormLabel htmlFor="confirmPassword">Confirm Password</FormLabel>
            <Input
              id="confirmPassword"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
            />
            {error && <FormErrorMessage>{error}</FormErrorMessage>}
          </FormControl>
          <Button
            type="submit"
            colorScheme="blue"
            w="full"
            isLoading={isSubmitting}
          >
            Sign Up
          </Button>
        </VStack>
      </form>
      <Text mt={4} fontSize="sm" textAlign="center">
        Already have an account?{" "}
        <ChakraLink as={NextLink} href="/login" color="blue.500">
          Log in
        </ChakraLink>
      </Text>
    </Box>
  );
}
