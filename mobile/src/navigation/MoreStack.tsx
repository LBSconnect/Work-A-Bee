import React from "react";
import { createNativeStackNavigator } from "@react-navigation/native-stack";

import MoreScreen from "../screens/employee/MoreScreen";
import PayStubsScreen from "../screens/employee/PayStubsScreen";
import PayStubDetailScreen from "../screens/employee/PayStubDetailScreen";
import TimeHistoryScreen from "../screens/employee/TimeHistoryScreen";
import ProfileScreen from "../screens/employee/ProfileScreen";
import AnnouncementsScreen from "../screens/employee/AnnouncementsScreen";
import NotificationsScreen from "../screens/employee/NotificationsScreen";

export type MoreStackParamList = {
  MoreMenu: undefined;
  PayStubs: undefined;
  PayStubDetail: { periodStart: string };
  TimeHistory: undefined;
  Profile: undefined;
  Announcements: undefined;
  Notifications: undefined;
};

const Stack = createNativeStackNavigator<MoreStackParamList>();

export default function MoreStackNavigator() {
  return (
    <Stack.Navigator>
      <Stack.Screen name="MoreMenu" component={MoreScreen} options={{ title: "More" }} />
      <Stack.Screen name="PayStubs" component={PayStubsScreen} options={{ title: "Pay Stubs" }} />
      <Stack.Screen name="PayStubDetail" component={PayStubDetailScreen} options={{ title: "Pay Stub" }} />
      <Stack.Screen name="TimeHistory" component={TimeHistoryScreen} options={{ title: "Time History" }} />
      <Stack.Screen name="Profile" component={ProfileScreen} options={{ title: "Profile" }} />
      <Stack.Screen name="Announcements" component={AnnouncementsScreen} options={{ title: "Announcements" }} />
      <Stack.Screen name="Notifications" component={NotificationsScreen} options={{ title: "Notifications" }} />
    </Stack.Navigator>
  );
}
