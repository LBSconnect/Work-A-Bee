import React from "react";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";

import AdminTodayScreen from "../screens/admin/AdminTodayScreen";
import AdminPtoScreen from "../screens/admin/AdminPtoScreen";
import AdminCorrectionsScreen from "../screens/admin/AdminCorrectionsScreen";
import AdminMoreScreen from "../screens/admin/AdminMoreScreen";

const Tab = createBottomTabNavigator();

export default function AdminTabs() {
  return (
    <Tab.Navigator screenOptions={{ tabBarActiveTintColor: "#a8641f" }}>
      <Tab.Screen name="Today" component={AdminTodayScreen} options={{ headerShown: false }} />
      <Tab.Screen name="PTO" component={AdminPtoScreen} options={{ headerShown: false }} />
      <Tab.Screen name="Corrections" component={AdminCorrectionsScreen} options={{ headerShown: false }} />
      <Tab.Screen name="More" component={AdminMoreScreen} options={{ headerShown: false }} />
    </Tab.Navigator>
  );
}
