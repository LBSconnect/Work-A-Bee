import React from "react";
import { ActivityIndicator, View } from "react-native";
import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";

import { useAuth } from "../auth/AuthContext";
import LoginScreen from "../screens/LoginScreen";
import ClockScreen from "../screens/employee/ClockScreen";
import AdminHomeScreen from "../screens/admin/AdminHomeScreen";

const Stack = createNativeStackNavigator();

export default function RootNavigator() {
  const { status, me } = useAuth();

  if (status === "loading") {
    return (
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center" }}>
        <ActivityIndicator size="large" color="#a8641f" />
      </View>
    );
  }

  return (
    <NavigationContainer>
      <Stack.Navigator screenOptions={{ headerShown: false }}>
        {status === "signedOut" || !me ? (
          <Stack.Screen name="Login" component={LoginScreen} />
        ) : me.role === "employee" ? (
          <Stack.Screen name="EmployeeClock" component={ClockScreen} />
        ) : (
          <Stack.Screen name="AdminHome" component={AdminHomeScreen} />
        )}
      </Stack.Navigator>
    </NavigationContainer>
  );
}
