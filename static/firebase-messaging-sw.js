// ==========================================
// LOKA PARTNER - FIREBASE SERVICE WORKER
// ==========================================

importScripts(
    "https://www.gstatic.com/firebasejs/13.1.0/firebase-app-compat.js"
);

importScripts(
    "https://www.gstatic.com/firebasejs/13.1.0/firebase-messaging-compat.js"
);

// Firebase configuration
firebase.initializeApp({
    apiKey: "AIzaSyAySx6DJ_gnw4JAPLsOixdiCEDCr7Xt73tLA",
    authDomain: "loka-marketplace.firebaseapp.com",
    projectId: "loka-marketplace",
    storageBucket: "loka-marketplace.firebasestorage.app",
    messagingSenderId: "54112834347",
    appId: "1:54112834347:web:5b5a8e61e673f5de812b6e"
});

// Initialize messaging
const messaging = firebase.messaging();

// Receive background notifications
messaging.onBackgroundMessage(function (payload) {

    console.log(
        "LOKA Partner background message:",
        payload
    );

    const data = payload.data || {};

    const title = data.title || "🔔 New LOKA Order!";

    const options = {

        body:
            "Order #" + (data.order_id || "") +
            "\nCustomer: " + (data.customer_name || "New customer") +
            "\nTotal: ₹" + (data.total || "0"),

        icon: "/static/images/loka-logo.png",

        badge: "/static/images/loka-logo.png",

        tag: "loka-order-" + (data.order_id || Date.now()),

        renotify: true,

        data: {
            url: "/partner/"
        }
    };

    self.registration.showNotification(
        title,
        options
    );

});

// Handle notification clicks
self.addEventListener("notificationclick", function (event) {

    event.notification.close();

    const targetUrl =
        event.notification.data?.url || "/partner/";

    event.waitUntil(

        clients.matchAll({
            type: "window",
            includeUncontrolled: true
        }).then(function (clientList) {

            for (const client of clientList) {

                if ("focus" in client) {

                    return client.focus().then(function (focusedClient) {

                        if ("navigate" in focusedClient) {
                            return focusedClient.navigate(targetUrl);
                        }

                        return focusedClient;
                    });
                }
            }

            return clients.openWindow(targetUrl);

        })

    );

});
