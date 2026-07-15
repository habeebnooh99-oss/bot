import org.telegram.telegrambots.bots.TelegramLongPollingBot;
import org.telegram.telegrambots.meta.TelegramBotsApi;
import org.telegram.telegrambots.meta.api.methods.send.SendMessage;
import org.telegram.telegrambots.meta.api.methods.updatingmessages.EditMessageText;
import org.telegram.telegrambots.meta.api.objects.CallbackQuery;
import org.telegram.telegrambots.meta.api.objects.Message;
import org.telegram.telegrambots.meta.api.objects.Update;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.InlineKeyboardMarkup;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.buttons.InlineKeyboardButton;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;
import org.telegram.telegrambots.updatesreceivers.DefaultBotSession;

import java.sql.*;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class AlexCardBot extends TelegramLongPollingBot {

    private static final String BOT_TOKEN = "8811163076:AAHlcXGmsZcAFQM_Or4jlVD-luIsDo9cxnI";
    private static final String BOT_USERNAME = "ALEX CARD";
    private static final long ADMIN_ID = 8529336745L;
    private static final String DB_URL = "jdbc:sqlite:alexcard.db";

    // لحفظ حالة المحادثة لكل مستخدم (FSM)
    private static final Map<Long, UserState> userStates = new HashMap<>();
    private static final Map<Long, String> tempInputs = new HashMap<>();

    public static void main(String[] args) {
        try {
            initDatabase();
            TelegramBotsApi botsApi = new TelegramBotsApi(DefaultBotSession.class);
            botsApi.registerBot(new AlexCardBot());
            System.out.println("🤖 Bot is successfully running!");
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    @Override
    public String getBotUsername() {
        return BOT_USERNAME;
    }

    @Override
    public String getBotToken() {
        return BOT_TOKEN;
    }

    // --- حالة المستخدمين المؤقتة ---
    enum UserState {
        NONE,
        WAITING_PRODUCT_INFO, // زبون: يرسل معلومات الشراء
        WAITING_ORANGE_MONEY, // زبون: يرسل نص تحويل أورنج موني
        WAITING_ADMIN_REJECT_REASON, // أدمن: سبب الرفض
        WAITING_ADMIN_ADD_BALANCE, // أدمن: كتابة الرصيد المراد إضافته
        WAITING_ADMIN_CAT_NAME, // أدمن: إضافة قسم
        WAITING_ADMIN_PROD_NAME, // أدمن: اسم المنتج
        WAITING_ADMIN_PROD_DESC, // أدمن: وصف المنتج
        WAITING_ADMIN_PROD_PRICE_JOD, // أدمن: سعر المنتج دينار
        WAITING_ADMIN_PROD_PRICE_USD, // أدمن: سعر المنتج دولار
        WAITING_BROADCAST_ALL, // أدمن: إعلان للكل
        WAITING_BROADCAST_ID, // أدمن: ايدي مستهدف للإعلان
        WAITING_BROADCAST_TARGET_MSG, // أدمن: رسالة الإعلان للشخص المحدد
        WAITING_DISCOUNT_ID, // أدمن: ايدي الزبون للخصم
        WAITING_DISCOUNT_PERCENT // أدمن: نسبة الخصم
    }

    // --- إعداد قاعدة البيانات ---
    private static void initDatabase() throws SQLException {
        try (Connection conn = DriverManager.getConnection(DB_URL);
             Statement stmt = conn.createStatement()) {
            
            // جدول المستخدمين
            stmt.execute("CREATE TABLE IF NOT EXISTS users (" +
                    "chat_id INTEGER PRIMARY KEY, " +
                    "username TEXT, " +
                    "balance_jod REAL DEFAULT 0.0, " +
                    "balance_usd REAL DEFAULT 0.0, " +
                    "discount REAL DEFAULT 0.0)");

            // جدول الأقسام (دعم متداخل غير محدود)
            stmt.execute("CREATE TABLE IF NOT EXISTS categories (" +
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, " +
                    "name TEXT, " +
                    "parent_id INTEGER DEFAULT 0)");

            // جدول المنتجات
            stmt.execute("CREATE TABLE IF NOT EXISTS products (" +
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, " +
                    "category_id INTEGER, " +
                    "name TEXT, " +
                    "description TEXT, " +
                    "price_jod REAL, " +
                    "price_usd REAL)");

            // جدول الطلبات
            stmt.execute("CREATE TABLE IF NOT EXISTS orders (" +
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, " +
                    "user_id INTEGER, " +
                    "product_id INTEGER, " +
                    "info TEXT, " +
                    "status TEXT DEFAULT 'PENDING')");
        }
    }

    @Override
    public void onUpdateReceived(Update update) {
        if (update.hasMessage() && update.getMessage().hasText()) {
            handleTextMessage(update.getMessage());
        } else if (update.hasCallbackQuery()) {
            handleCallbackQuery(update.getCallbackQuery());
        }
    }

    // --- معالجة الرسائل النصية ---
    private void handleTextMessage(Message message) {
        long chatId = message.getChatId();
        String text = message.getText();

        // تسجيل دخول تلقائي للمستخدم
        registerUser(chatId, message.getFrom().getFirstName());

        if (text.equals("/start")) {
            userStates.put(chatId, UserState.NONE);
            sendMainMenu(chatId);
            return;
        }

        UserState state = userStates.getOrDefault(chatId, UserState.NONE);

        // --- معالجة مدخلات الأدمن ---
        if (chatId == ADMIN_ID) {
            switch (state) {
                case WAITING_ADMIN_CAT_NAME:
                    String parentIdStr = tempInputs.get(chatId);
                    int parentId = parentIdStr != null ? Integer.parseInt(parentIdStr) : 0;
                    addCategory(text, parentId);
                    sendMessage(chatId, "✅ تم إضافة القسم بنجاح!");
                    userStates.put(chatId, UserState.NONE);
                    sendMainMenu(chatId);
                    break;

                case WAITING_ADMIN_PROD_NAME:
                    tempInputs.put(chatId, tempInputs.get(chatId) + ":::" + text); // categoryId:::name
                    sendMessage(chatId, "📝 أرسل وصف المنتج الآن:");
                    userStates.put(chatId, UserState.WAITING_ADMIN_PROD_DESC);
                    break;

                case WAITING_ADMIN_PROD_DESC:
                    tempInputs.put(chatId, tempInputs.get(chatId) + ":::" + text); // categoryId:::name:::desc
                    sendMessage(chatId, "💰 أرسل سعر المنتج بالدينار الأردني (JOD) - رقم فقط:");
                    userStates.put(chatId, UserState.WAITING_ADMIN_PROD_PRICE_JOD);
                    break;

                case WAITING_ADMIN_PROD_PRICE_JOD:
                    tempInputs.put(chatId, tempInputs.get(chatId) + ":::" + text); // categoryId:::name:::desc:::priceJod
                    sendMessage(chatId, "💵 أرسل سعر المنتج بالدولار (USD) - رقم فقط:");
                    userStates.put(chatId, UserState.WAITING_ADMIN_PROD_PRICE_USD);
                    break;

                case WAITING_ADMIN_PROD_PRICE_USD:
                    String[] parts = tempInputs.get(chatId).split(":::");
                    int catId = Integer.parseInt(parts[0]);
                    String prodName = parts[1];
                    String desc = parts[2];
                    double jPrice = Double.parseDouble(parts[3]);
                    double uPrice = Double.parseDouble(text);
                    addProduct(catId, prodName, desc, jPrice, uPrice);
                    sendMessage(chatId, "✅ تم إضافة المنتج بنجاح بنجاح!");
                    userStates.put(chatId, UserState.NONE);
                    sendMainMenu(chatId);
                    break;

                case WAITING_ADMIN_ADD_BALANCE:
                    String[] chargeParts = tempInputs.get(chatId).split(":::");
                    long targetUser = Long.parseLong(chargeParts[0]);
                    int orderId = Integer.parseInt(chargeParts[1]);
                    try {
                        double amountUsd = Double.parseDouble(text);
                        double amountJod = amountUsd * 0.71; // تقريب سعر الصرف المعتمد
                        updateUserBalance(targetUser, amountJod, amountUsd);
                        updateOrderStatus(orderId, "ACCEPTED");
                        sendMessage(chatId, "✅ تم شحن رصيد المستخدم بنجاح بقيمة " + amountUsd + " $");
                        sendMessage(targetUser, "🎉 تم قبول طلب الشحن وإضافة رصيد لحسابك بقيمة: " + amountUsd + " $ (" + amountJod + " د.أ)");
                    } catch (NumberFormatException e) {
                        sendMessage(chatId, "⚠️ يرجى إدخال رقم صحيح.");
                    }
                    userStates.put(chatId, UserState.NONE);
                    break;

                case WAITING_BROADCAST_ALL:
                    broadcastToAll(text);
                    sendMessage(chatId, "✅ تم إرسال الإعلان لجميع المشتركين!");
                    userStates.put(chatId, UserState.NONE);
                    break;

                case WAITING_BROADCAST_ID:
                    tempInputs.put(chatId, text); // حفظ آيدي المستهدف
                    sendMessage(chatId, "💬 أرسل محتوى الرسالة الآن لتبليغه بها:");
                    userStates.put(chatId, UserState.WAITING_BROADCAST_TARGET_MSG);
                    break;

                case WAITING_BROADCAST_TARGET_MSG:
                    long targetId = Long.parseLong(tempInputs.get(chatId));
                    sendMessage(targetId, "📢 رسالة من الإدارة:\n\n" + text);
                    sendMessage(chatId, "✅ تم إرسال الرسالة إلى العضو بنجاح.");
                    userStates.put(chatId, UserState.NONE);
                    break;

                case WAITING_DISCOUNT_ID:
                    tempInputs.put(chatId, text); // حفظ آيدي الزبون للخصم
                    sendMessage(chatId, "📉 أرسل نسبة الخصم المئوية (مثال: 10 للخصم 10%):");
                    userStates.put(chatId, UserState.WAITING_DISCOUNT_PERCENT);
                    break;

                case WAITING_DISCOUNT_PERCENT:
                    long dUserId = Long.parseLong(tempInputs.get(chatId));
                    double discVal = Double.parseDouble(text);
                    updateUserDiscount(dUserId, discVal);
                    sendMessage(chatId, "✅ تم تعيين نسبة خصم بقيمة " + discVal + "% للمستخدم بنجاح.");
                    sendMessage(dUserId, "🎁 لقد منحتك الإدارة خصماً خاصاً بنسبة: " + discVal + "% على كافة خدماتنا!");
                    userStates.put(chatId, UserState.NONE);
                    break;
            }
        }

        // --- معالجة مدخلات الزبون ---
        if (chatId != ADMIN_ID || state == UserState.WAITING_PRODUCT_INFO || state == UserState.WAITING_ORANGE_MONEY) {
            switch (state) {
                case WAITING_PRODUCT_INFO:
                    String[] buyParts = tempInputs.get(chatId).split(":::");
                    int prodId = Integer.parseInt(buyParts[0]);
                    int dbOrderId = createOrder(chatId, prodId, text);
                    
                    sendMessage(chatId, "⏳ تم إرسال طلب الشراء للإدارة بنجاح وهو تحت المراجعة حالياً.");
                    
                    // إشعار للأدمن
                    String adminMsg = "📦 *طلب شراء جديد!*\n" +
                            "👤 العميل: ` " + chatId + " `\n" +
                            "🛍️ المنتج: " + getProductName(prodId) + "\n" +
                            "📝 البيانات المرسلة: \n" + text;
                    
                    InlineKeyboardMarkup markup = new InlineKeyboardMarkup();
                    List<List<InlineKeyboardButton>> rows = new ArrayList<>();
                    List<InlineKeyboardButton> row = new ArrayList<>();
                    
                    InlineKeyboardButton accBtn = new InlineKeyboardButton("✅ قبول الطلب");
                    accBtn.setCallbackData("ADMIN_ACCEPT_PROD_" + dbOrderId + "_" + chatId + "_" + prodId);
                    InlineKeyboardButton rejBtn = new InlineKeyboardButton("❌ رفض الطلب");
                    rejBtn.setCallbackData("ADMIN_REJECT_PROD_" + dbOrderId + "_" + chatId);
                    
                    row.add(accBtn);
                    row.add(rejBtn);
                    rows.add(row);
                    markup.setKeyboard(rows);
                    
                    sendAdminMessageWithMarkup(adminMsg, markup);
                    userStates.put(chatId, UserState.NONE);
                    break;

                case WAITING_ORANGE_MONEY:
                    int rechargeOrderId = createRechargeRequest(chatId, text);
                    sendMessage(chatId, "⏳ تم إرسال نص التحويل للإدارة بنجاح. سيتم مراجعته وشحن حسابك فوراً.");
                    
                    String rAdminMsg = "💰 *طلب شحن رصيد أورنج موني!*\n" +
                            "👤 العميل: ` " + chatId + " `\n" +
                            "📄 نص الحوالة المستلم:\n" + text;
                    
                    InlineKeyboardMarkup rMarkup = new InlineKeyboardMarkup();
                    List<List<InlineKeyboardButton>> rRows = new ArrayList<>();
                    List<InlineKeyboardButton> rRow = new ArrayList<>();
                    
                    InlineKeyboardButton rAccBtn = new InlineKeyboardButton("✅ قبول وشحن");
                    rAccBtn.setCallbackData("ADMIN_ACCEPT_CHARGE_" + rechargeOrderId + "_" + chatId);
                    InlineKeyboardButton rRejBtn = new InlineKeyboardButton("❌ رفض");
                    rRejBtn.setCallbackData("ADMIN_REJECT_CHARGE_" + rechargeOrderId + "_" + chatId);
                    
                    rRow.add(rAccBtn);
                    rRow.add(rRejBtn);
                    rRows.add(rRow);
                    rMarkup.setKeyboard(rRows);
                    
                    sendAdminMessageWithMarkup(rAdminMsg, rMarkup);
                    userStates.put(chatId, UserState.NONE);
                    break;
            }
        }
    }

    // --- معالجة نقرات الأزرار ---
    private void handleCallbackQuery(CallbackQuery callbackQuery) {
        long chatId = callbackQuery.getMessage().getChatId();
        String data = callbackQuery.getData();
        int messageId = callbackQuery.getMessage().getMessageId();

        if (data.equals("MENU_STORE")) {
            showCategoriesMenu(chatId, 0, messageId);
        } else if (data.startsWith("VIEW_CAT_")) {
            int catId = Integer.parseInt(data.substring(9));
            showCategoriesMenu(chatId, catId, messageId);
        } else if (data.startsWith("VIEW_PROD_")) {
            int prodId = Integer.parseInt(data.substring(10));
            showProductDetails(chatId, prodId, messageId);
        } else if (data.startsWith("BUY_PROD_")) {
            int prodId = Integer.parseInt(data.substring(9));
            tempInputs.put(chatId, String.valueOf(prodId));
            editMessage(chatId, messageId, "📥 يرجى إرسال المعلومات المطلوبة لإتمام عملية الشراء:");
            userStates.put(chatId, UserState.WAITING_PRODUCT_INFO);
        } else if (data.equals("MENU_MY_ACCOUNT")) {
            showMyAccount(chatId, messageId);
        } else if (data.equals("MENU_MY_ORDERS")) {
            showMyOrders(chatId, messageId);
        } else if (data.equals("MENU_RECHARGE")) {
            showRechargeMenu(chatId, messageId);
        } else if (data.equals("RECHARGE_ORANGE")) {
            showOrangeMoneyDetails(chatId, messageId);
        } else if (data.equals("RECHARGE_ALL")) {
            showAllCountriesDetails(chatId, messageId);
        } else if (data.equals("MENU_SUPPORT")) {
            showSupportDetails(chatId, messageId);
        } else if (data.equals("BACK_TO_MAIN")) {
            userStates.put(chatId, UserState.NONE);
            showMainMenuBack(chatId, messageId);
        }

        // --- أزرار الإدارة الخاصة بالآدمن ---
        if (chatId == ADMIN_ID) {
            if (data.equals("ADMIN_PANEL")) {
                showAdminPanel(chatId, messageId);
            } else if (data.startsWith("ADMIN_ADD_CAT_")) {
                int parentId = Integer.parseInt(data.substring(14));
                tempInputs.put(chatId, String.valueOf(parentId));
                editMessage(chatId, messageId, "➕ أرسل الآن اسم القسم الجديد لإنشائه:");
                userStates.put(chatId, UserState.WAITING_ADMIN_CAT_NAME);
            } else if (data.startsWith("ADMIN_ADD_PROD_")) {
                int catId = Integer.parseInt(data.substring(15));
                tempInputs.put(chatId, String.valueOf(catId));
                editMessage(chatId, messageId, "➕ أرسل الآن اسم المنتج الجديد:");
                userStates.put(chatId, UserState.WAITING_ADMIN_PROD_NAME);
            } else if (data.startsWith("ADMIN_DEL_CAT_")) {
                int catId = Integer.parseInt(data.substring(14));
                deleteCategory(catId);
                editMessage(chatId, messageId, "❌ تم حذف القسم ومحتوياته بنجاح.");
            } else if (data.startsWith("ADMIN_DEL_PROD_")) {
                int prodId = Integer.parseInt(data.substring(15));
                deleteProduct(prodId);
                editMessage(chatId, messageId, "❌ تم حذف المنتج بنجاح.");
            } else if (data.startsWith("ADMIN_ACCEPT_PROD_")) {
                // ADMIN_ACCEPT_PROD_{orderId}_{userId}_{prodId}
                String[] parts = data.split("_");
                int orderId = Integer.parseInt(parts[3]);
                long userId = Long.parseLong(parts[4]);
                int prodId = Integer.parseInt(parts[5]);
                processProductPurchaseAccept(orderId, userId, prodId);
            } else if (data.startsWith("ADMIN_REJECT_PROD_")) {
                String[] parts = data.split("_");
                int orderId = Integer.parseInt(parts[3]);
                long userId = Long.parseLong(parts[4]);
                updateOrderStatus(orderId, "REJECTED");
                sendMessage(userId, "❌ تم رفض طلب الشراء الخاص بك. يرجى التواصل مع الإدارة للتوضيح.");
                sendMessage(ADMIN_ID, "🛑 تم إرسال إشعار بالرفض للزبون بنجاح.");
            } else if (data.startsWith("ADMIN_ACCEPT_CHARGE_")) {
                String[] parts = data.split("_");
                int orderId = Integer.parseInt(parts[3]);
                long userId = Long.parseLong(parts[4]);
                tempInputs.put(ADMIN_ID, userId + ":::" + orderId);
                sendMessage(ADMIN_ID, "💵 أرسل قيمة الرصيد بالدولار ($) المراد إضافته لحساب العميل:");
                userStates.put(ADMIN_ID, UserState.WAITING_ADMIN_ADD_BALANCE);
            } else if (data.startsWith("ADMIN_REJECT_CHARGE_")) {
                String[] parts = data.split("_");
                int orderId = Integer.parseInt(parts[3]);
                long userId = Long.parseLong(parts[4]);
                updateOrderStatus(orderId, "REJECTED");
                sendMessage(userId, "❌ تم رفض طلب شحن الرصيد. يرجى الاتصال بالدعم الفني.");
                sendMessage(ADMIN_ID, "🛑 تم رفض طلب الشحن وإعلام العميل.");
            } else if (data.equals("ADMIN_USER_LIST")) {
                showUsersList(chatId, messageId);
            } else if (data.equals("ADMIN_BROADCAST_MENU")) {
                showBroadcastMenu(chatId, messageId);
            } else if (data.equals("BROADCAST_ALL")) {
                editMessage(chatId, messageId, "📢 أرسل نص الإعلان الذي ترغب بنشره لجميع مستخدمي البوت:");
                userStates.put(chatId, UserState.WAITING_BROADCAST_ALL);
            } else if (data.equals("BROADCAST_SPECIFIC")) {
                editMessage(chatId, messageId, "🆔 أرسل الـ ID الخاص بالمستخدم المستهدف بالرسالة أولاً:");
                userStates.put(chatId, UserState.WAITING_BROADCAST_ID);
            } else if (data.equals("ADMIN_DISCOUNT_MENU")) {
                editMessage(chatId, messageId, "🆔 أرسل الـ ID للزبون المراد منحه الخصم المخصص:");
                userStates.put(chatId, UserState.WAITING_DISCOUNT_ID);
            }
        }
    }

    // --- عرض القائمة الرئيسية ---
    private void sendMainMenu(long chatId) {
        SendMessage sm = new SendMessage();
        sm.setChatId(String.valueOf(chatId));
        sm.setText("👋 مرحباً بك في بوت *" + BOT_USERNAME + "* للتجارة الرقمية!\nاستخدم الأزرار أدناه للتنقل بسلاسة:");
        sm.setParseMode("Markdown");
        sm.setReplyMarkup(getMainMenuMarkup(chatId));
        try {
            execute(sm);
        } catch (TelegramApiException e) {
            e.printStackTrace();
        }
    }

    private void showMainMenuBack(long chatId, int messageId) {
        EditMessageText em = new EditMessageText();
        em.setChatId(String.valueOf(chatId));
        em.setMessageId(messageId);
        em.setText("👋 مرحباً بك في بوت *" + BOT_USERNAME + "* للتجارة الرقمية!\nاستخدم الأزرار أدناه للتنقل بسلاسة:");
        em.setParseMode("Markdown");
        em.setReplyMarkup(getMainMenuMarkup(chatId));
        try {
            execute(em);
        } catch (TelegramApiException e) {
            e.printStackTrace();
        }
    }

    private InlineKeyboardMarkup getMainMenuMarkup(long chatId) {
        InlineKeyboardMarkup markup = new InlineKeyboardMarkup();
        List<List<InlineKeyboardButton>> rows = new ArrayList<>();

        List<InlineKeyboardButton> r1 = new ArrayList<>();
        InlineKeyboardButton btnStore = new InlineKeyboardButton("🛍️ المتجر");
        btnStore.setCallbackData("MENU_STORE");
        r1.add(btnStore);

        List<InlineKeyboardButton> r2 = new ArrayList<>();
        InlineKeyboardButton btnAcc = new InlineKeyboardButton("👤 حسابي");
        btnAcc.setCallbackData("MENU_MY_ACCOUNT");
        InlineKeyboardButton btnOrders = new InlineKeyboardButton("📦 طلباتي");
        btnOrders.setCallbackData("MENU_MY_ORDERS");
        r2.add(btnAcc);
        r2.add(btnOrders);

        List<InlineKeyboardButton> r3 = new ArrayList<>();
        InlineKeyboardButton btnRecharge = new InlineKeyboardButton("💳 شحن الرصيد");
        btnRecharge.setCallbackData("MENU_RECHARGE");
        InlineKeyboardButton btnSupport = new InlineKeyboardButton("🛠️ الدعم الفني");
        btnSupport.setCallbackData("MENU_SUPPORT");
        r3.add(btnRecharge);
        r3.add(btnSupport);

        rows.add(r1);
        rows.add(r2);
        rows.add(r3);

        // إذا كان المطور هو الأدمن
        if (chatId == ADMIN_ID) {
            List<InlineKeyboardButton> rAdmin = new ArrayList<>();
            InlineKeyboardButton btnAdmin = new InlineKeyboardButton("⚙️ لوحة الإدارة (الآدمن)");
            btnAdmin.setCallbackData("ADMIN_PANEL");
            rAdmin.add(btnAdmin);
            rows.add(rAdmin);
        }

        markup.setKeyboard(rows);
        return markup;
    }

    // --- شاشات وأقسام المتجر ---
    private void showCategoriesMenu(long chatId, int parentId, int messageId) {
        EditMessageText em = new EditMessageText();
        em.setChatId(String.valueOf(chatId));
        em.setMessageId(messageId);
        em.setText("📂 *الأقسام المتاحة حالياً:*\nاختر تصفح الأقسام أو حدد منتجاً للشراء:");
        em.setParseMode("Markdown");

        InlineKeyboardMarkup markup = new InlineKeyboardMarkup();
        List<List<InlineKeyboardButton>> rows = new ArrayList<>();

        // جلب الأقسام المتفرعة من الـ parentId الحالي
        try (Connection conn = DriverManager.getConnection(DB_URL);
             PreparedStatement ps = conn.prepareStatement("SELECT * FROM categories WHERE parent_id = ?")) {
            ps.setInt(1, parentId);
            ResultSet rs = ps.executeQuery();
            while (rs.next()) {
                List<InlineKeyboardButton> row = new ArrayList<>();
                InlineKeyboardButton btn = new InlineKeyboardButton("📁 " + rs.getString("name"));
                btn.setCallbackData("VIEW_CAT_" + rs.getInt("id"));
                row.add(btn);
                
                // إذا كان آدمن، إمكانية حذف القسم
                if (chatId == ADMIN_ID) {
                    InlineKeyboardButton delBtn = new InlineKeyboardButton("❌");
                    delBtn.setCallbackData("ADMIN_DEL_CAT_" + rs.getInt("id"));
                    row.add(delBtn);
                }
                rows.add(row);
            }
        } catch (SQLException e) {
            e.printStackTrace();
        }

        // جلب المنتجات التابعة للقسم الحالي
        try (Connection conn = DriverManager.getConnection(DB_URL);
             PreparedStatement ps = conn.prepareStatement("SELECT * FROM products WHERE category_id = ?")) {
            ps.setInt(1, parentId);
            ResultSet rs = ps.executeQuery();
            while (rs.next()) {
                List<InlineKeyboardButton> row = new ArrayList<>();
                InlineKeyboardButton btn = new InlineKeyboardButton("🎮 " + rs.getString("name") + " (" + rs.getDouble("price_usd") + "$)");
                btn.setCallbackData("VIEW_PROD_" + rs.getInt("id"));
                row.add(btn);

                if (chatId == ADMIN_ID) {
                    InlineKeyboardButton delBtn = new InlineKeyboardButton("❌");
                    delBtn.setCallbackData("ADMIN_DEL_PROD_" + rs.getInt("id"));
                    row.add(delBtn);
                }
                rows.add(row);
            }
        } catch (SQLException e) {
            e.printStackTrace();
        }

        // أزرار التحكم والرجوع للآدمن لإضافة المحتوى مباشرة في هذا القسم
        if (chatId == ADMIN_ID) {
            List<InlineKeyboardButton> adminRow = new ArrayList<>();
            InlineKeyboardButton addCat = new InlineKeyboardButton("➕ إضافة قسم فرعي");
            addCat.setCallbackData("ADMIN_ADD_CAT_" + parentId);
            InlineKeyboardButton addProd = new InlineKeyboardButton("➕ إضافة منتج");
            addProd.setCallbackData("ADMIN_ADD_PROD_" + parentId);
            adminRow.add(addCat);
            adminRow.add(addProd);
            rows.add(adminRow);
        }

        // زر الرجوع
        List<InlineKeyboardButton> backRow = new ArrayList<>();
        InlineKeyboardButton btnBack;
        if (parentId == 0) {
            btnBack = new InlineKeyboardButton("🔙 الرجوع للقائمة الرئيسية");
            btnBack.setCallbackData("BACK_TO_MAIN");
        } else {
            int grandpaId = getParentCategoryId(parentId);
            btnBack = new InlineKeyboardButton("🔙 الرجوع للقسم السابق");
            btnBack.setCallbackData("VIEW_CAT_" + grandpaId);
        }
        backRow.add(btnBack);
        rows.add(backRow);

        markup.setKeyboard(rows);
        em.setReplyMarkup(markup);

        try {
            execute(em);
        } catch (TelegramApiException e) {
            e.printStackTrace();
        }
    }

    private void showProductDetails(long chatId, int prodId, int messageId) {
        EditMessageText em = new EditMessageText();
        em.setChatId(String.valueOf(chatId));
        em.setMessageId(messageId);
        em.setParseMode("Markdown");

        double discountPercent = getUserDiscount(chatId);

        try (Connection conn = DriverManager.getConnection(DB_URL);
             PreparedStatement ps = conn.prepareStatement("SELECT * FROM products WHERE id = ?")) {
            ps.setInt(1, prodId);
            ResultSet rs = ps.executeQuery();
            if (rs.next()) {
                String name = rs.getString("name");
                String desc = rs.getString("description");
                double priceJod = rs.getDouble("price_jod");
                double priceUsd = rs.getDouble("price_usd");
                int catId = rs.getInt("category_id");

                // حساب الخصومات إذا وجدت للزبون
                double finalJod = priceJod * (1 - (discountPercent / 100));
                double finalUsd = priceUsd * (1 - (discountPercent / 100));

                StringBuilder sb = new StringBuilder();
                sb.append("📦 *").append(name).append("*\n\n");
                sb.append("📝 *الوصف:* ").append(desc).append("\n\n");
                
                if (discountPercent > 0) {
                    sb.append("⚠️ *لديك خصم خاص بقيمة: ").append(discountPercent).append("%*\n");
                    sb.append("💵 *السعر الأصلي:* ").append(priceJod).append(" د.أ / ").append(priceUsd).append(" $\n");
                    sb.append("🔥 *السعر بعد الخصم:* `").append(String.format("%.2f", finalJod)).append(" د.أ` / `").append(String.format("%.2f", finalUsd)).append(" $`\n");
                } else {
                    sb.append("💵 *السعر المعتمد:* `").append(priceJod).append(" د.أ` / `").append(priceUsd).append(" $`\n");
                }

                em.setText(sb.toString());

                InlineKeyboardMarkup markup = new InlineKeyboardMarkup();
                List<List<InlineKeyboardButton>> rows = new ArrayList<>();

                List<InlineKeyboardButton> r1 = new ArrayList<>();
                InlineKeyboardButton buyBtn = new InlineKeyboardButton("💳 شراء الآن");
                buyBtn.setCallbackData("BUY_PROD_" + prodId);
                r1.add(buyBtn);

                List<InlineKeyboardButton> r2 = new ArrayList<>();
                InlineKeyboardButton backBtn = new InlineKeyboardButton("🔙 رجوع");
                backBtn.setCallbackData("VIEW_CAT_" + catId);
                r2.add(backBtn);

                rows.add(r1);
                rows.add(r2);
                markup.setKeyboard(rows);
                em.setReplyMarkup(markup);
            }
        } catch (SQLException | TelegramApiException e) {
            e.printStackTrace();
        }

        try {
            execute(em);
        } catch (TelegramApiException e) {
            e.printStackTrace();
        }
    }

    // --- حسابي والدعم وباقي الأقسام للزبائن ---
    private void showMyAccount(long chatId, int messageId) {
        EditMessageText em = new EditMessageText();
        em.setChatId(String.valueOf(chatId));
        em.setMessageId(messageId);
        em.setParseMode("Markdown");

        try (Connection conn = DriverManager.getConnection(DB_URL);
             PreparedStatement ps = conn.prepareStatement("SELECT * FROM users WHERE chat_id = ?")) {
            ps.setLong(1, chatId);
            ResultSet rs = ps.executeQuery();
            if (rs.next()) {
                String text = "👤 *تفاصيل حسابك الشخصي:*\n\n" +
                        "🆔 الآيدي الخاص بك: `" + chatId + "`\n" +
                        "📛 الاسم: *" + rs.getString("username") + "*\n\n" +
                        "💰 *الرصيد المتاح:*\n" +
                        "💵 بالدولار: `" + rs.getDouble("balance_usd") + " $`\n" +
                        "🇯🇴 بالدينار الأردني: `" + rs.getDouble("balance_jod") + " د.أ`\n\n" +
                        "📉 نسبة الخصم المعتمدة لك: `%" + rs.getDouble("discount") + "`";
                em.setText(text);
            }
        } catch (SQLException e) {
            e.printStackTrace();
        }

        InlineKeyboardMarkup markup = new InlineKeyboardMarkup();
        List<List<InlineKeyboardButton>> rows = new ArrayList<>();
        List<InlineKeyboardButton> row = new ArrayList<>();
        InlineKeyboardButton btnBack = new InlineKeyboardButton("🔙 الرجوع للقائمة الرئيسية");
        btnBack.setCallbackData("BACK_TO_MAIN");
        row.add(btnBack);
        rows.add(row);
        markup.setKeyboard(rows);
        em.setReplyMarkup(markup);

        try {
            execute(em);
        } catch (TelegramApiException e) {
            e.printStackTrace();
        }
    }

    private void showMyOrders(long chatId, int messageId) {
        EditMessageText em = new EditMessageText();
        em.setChatId(String.valueOf(chatId));
        em.setMessageId(messageId);
        em.setParseMode("Markdown");

        StringBuilder sb = new StringBuilder();
        sb.append("📦 *طلباتك الحالية تحت المراجعة:*\n\n");

        boolean hasOrders = false;
        try (Connection conn = DriverManager.getConnection(DB_URL);
             PreparedStatement ps = conn.prepareStatement(
                     "SELECT o.id, p.name, o.info FROM orders o JOIN products p ON o.product_id = p.id " +
                             "WHERE o.user_id = ? AND o.status = 'PENDING'")) {
            ps.setLong(1, chatId);
            ResultSet rs = ps.executeQuery();
            while (rs.next()) {
                hasOrders = true;
                sb.append("🔹 *طلب رقم:* `").append(rs.getInt("id")).append("`\n")
                        .append("🛍️ *المنتج:* ").append(rs.getString("name")).append("\n")
                        .append("📄 *البيانات:* ").append(rs.getString("info")).append("\n\n");
            }
        } catch (SQLException e) {
            e.printStackTrace();
        }

        if (!hasOrders) {
            sb.append("⚠️ لا يوجد لديك أي طلبات تحت المراجعة حالياً.");
        }

        em.setText(sb.toString());

        InlineKeyboardMarkup markup = new InlineKeyboardMarkup();
        List<List<InlineKeyboardButton>> rows = new ArrayList<>();
        List<InlineKeyboardButton> row = new ArrayList<>();
        InlineKeyboardButton btnBack = new InlineKeyboardButton("🔙 الرجوع للقائمة الرئيسية");
        btnBack.setCallbackData("BACK_TO_MAIN");
        row.add(btnBack);
        rows.add(row);
        markup.setKeyboard(rows);
        em.setReplyMarkup(markup);

        try {
            execute(em);
        } catch (TelegramApiException e) {
            e.printStackTrace();
        }
    }

    private void showRechargeMenu(long chatId, int messageId) {
        EditMessageText em = new EditMessageText();
        em.setChatId(String.valueOf(chatId));
        em.setMessageId(messageId);
        em.setText("💳 *اختر وسيلة الشحن المناسبة لك:*");
        em.setParseMode("Markdown");

        InlineKeyboardMarkup markup = new InlineKeyboardMarkup();
        List<List<InlineKeyboardButton>> rows = new ArrayList<>();

        List<InlineKeyboardButton> r1 = new ArrayList<>();
        InlineKeyboardButton btnOrange = new InlineKeyboardButton("🍊 محفظة أورنج موني");
        btnOrange.setCallbackData("RECHARGE_ORANGE");
        r1.add(btnOrange);

        List<InlineKeyboardButton> r2 = new ArrayList<>();
        InlineKeyboardButton btnAll = new InlineKeyboardButton("🌍 الشحن للدول العربية والأجنبية");
        btnAll.setCallbackData("RECHARGE_ALL");
        r2.add(btnAll);

        List<InlineKeyboardButton> r3 = new ArrayList<>();
        InlineKeyboardButton btnBack = new InlineKeyboardButton("🔙 الرجوع للقائمة الرئيسية");
        btnBack.setCallbackData("BACK_TO_MAIN");
        r3.add(btnBack);

        rows.add(r1);
        rows.add(r2);
        rows.add(r3);
        markup.setKeyboard(rows);
        em.setReplyMarkup(markup);

        try {
            execute(em);
        } catch (TelegramApiException e) {
            e.printStackTrace();
        }
    }

    private void showOrangeMoneyDetails(long chatId, int messageId) {
        EditMessageText em = new EditMessageText();
        em.setChatId(String.valueOf(chatId));
        em.setMessageId(messageId);
        em.setParseMode("Markdown");

        String msg = "🍊 *طريقة الشحن عبر محفظة أورنج موني:*\n\n" +
                "👤 اسم المحفظة: `سلمان نوح سلمان البدارين`\n" +
                "📱 رقم المحفظة: `0776445110`\n" +
                "🏢 المحفظة: *أورنج موني*\n\n" +
                "📥 *الخطوة التالية:*\n" +
                "يرجى إرسال نص رسالة التحويل البنكي المستلمة من المحفظة مباشرة لتأكيد الدفع وشحن حسابك فورا.";

        em.setText(msg);

        InlineKeyboardMarkup markup = new InlineKeyboardMarkup();
        List<List<InlineKeyboardButton>> rows = new ArrayList<>();
        List<InlineKeyboardButton> row = new ArrayList<>();
        InlineKeyboardButton btnBack = new InlineKeyboardButton("🔙 رجوع");
        btnBack.setCallbackData("MENU_RECHARGE");
        row.add(btnBack);
        rows.add(row);
        markup.setKeyboard(rows);
        em.setReplyMarkup(markup);

        try {
            execute(em);
            userStates.put(chatId, UserState.WAITING_ORANGE_MONEY);
        } catch (TelegramApiException e) {
            e.printStackTrace();
        }
    }

    private void showAllCountriesDetails(long chatId, int messageId) {
        EditMessageText em = new EditMessageText();
        em.setChatId(String.valueOf(chatId));
        em.setMessageId(messageId);
        em.setParseMode("Markdown");

        String msg = "🌍 *الشحن لجميع الدول العربية والأجنبية:*\n\n" +
                "نوفر طرق دفع متعددة تناسب بلدك (سواء كنت في سوريا، مصر، العراق، أو أي دولة أخرى).\n\n" +
                "📥 يرجى التواصل مع الإدارة مباشرة وإرسال اسم بلدك ليتم تزويدك بطرق التحويل المتاحة لك فوراً.\n\n" +
                "🔗 *للتواصل المباشر مع الإدارة:* \n" +
                "تليجرام: @htb1b";

        em.setText(msg);

        InlineKeyboardMarkup markup = new InlineKeyboardMarkup();
        List<List<InlineKeyboardButton>> rows = new ArrayList<>();
        List<InlineKeyboardButton> row = new ArrayList<>();
        InlineKeyboardButton btnBack = new InlineKeyboardButton("🔙 رجوع");
        btnBack.setCallbackData("MENU_RECHARGE");
        row.add(btnBack);
        rows.add(row);
        markup.setKeyboard(rows);
        em.setReplyMarkup(markup);

        try {
            execute(em);
        } catch (TelegramApiException e) {
            e.printStackTrace();
        }
    }

    private void showSupportDetails(long chatId, int messageId) {
        EditMessageText em = new EditMessageText();
        em.setChatId(String.valueOf(chatId));
        em.setMessageId(messageId);
        em.setParseMode("Markdown");

        String msg = "🛠️ *قسم الدعم الفني:*\n\n" +
                "📞 رقم الواتساب: +962776445110\n" +
                "✈️ التليجرام: htb1b@";

        em.setText(msg);

        InlineKeyboardMarkup markup = new InlineKeyboardMarkup();
        List<List<InlineKeyboardButton>> rows = new ArrayList<>();
        List<InlineKeyboardButton> row = new ArrayList<>();
        InlineKeyboardButton btnBack = new InlineKeyboardButton("🔙 الرجوع للقائمة الرئيسية");
        btnBack.setCallbackData("BACK_TO_MAIN");
        row.add(btnBack);
        rows.add(row);
        markup.setKeyboard(rows);
        em.setReplyMarkup(markup);

        try {
            execute(em);
        } catch (TelegramApiException e) {
            e.printStackTrace();
        }
    }

    // --- لوحة التحكم الخاصة بالأدمن ---
    private void showAdminPanel(long chatId, int messageId) {
        EditMessageText em = new EditMessageText();
        em.setChatId(String.valueOf(chatId));
        em.setMessageId(messageId);
        em.setText("🛠️ *مرحباً بك في لوحة الإدارة والتحكم (الآدمن):*");
        em.setParseMode("Markdown");

        InlineKeyboardMarkup markup = new InlineKeyboardMarkup();
        List<List<InlineKeyboardButton>> rows = new ArrayList<>();

        List<InlineKeyboardButton> r1 = new ArrayList<>();
        InlineKeyboardButton btn1 = new InlineKeyboardButton("📁 إدارة وتعديل المتجر");
        btn1.setCallbackData("MENU_STORE");
        r1.add(btn1);

        List<InlineKeyboardButton> r2 = new ArrayList<>();
        InlineKeyboardButton btn2 = new InlineKeyboardButton("👥 قائمة المشتركين");
        btn2.setCallbackData("ADMIN_USER_LIST");
        InlineKeyboardButton btn3 = new InlineKeyboardButton("📉 إعداد الخصومات للزبائن");
        btn3.setCallbackData("ADMIN_DISCOUNT_MENU");
        r2.add(btn2);
        r2.add(btn3);

        List<InlineKeyboardButton> r3 = new ArrayList<>();
        InlineKeyboardButton btn4 = new InlineKeyboardButton("📢 إرسال إعلان / بث");
        btn4.setCallbackData("ADMIN_BROADCAST_MENU");
        r3.add(btn4);

        List<InlineKeyboardButton> r4 = new ArrayList<>();
        InlineKeyboardButton btnBack = new InlineKeyboardButton("🔙 الرجوع للواجهة الرئيسية للزبون");
        btnBack.setCallbackData("BACK_TO_MAIN");
        r4.add(btnBack);

        rows.add(r1);
        rows.add(r2);
        rows.add(r3);
        rows.add(r4);
        markup.setKeyboard(rows);
        em.setReplyMarkup(markup);

        try {
            execute(em);
        } catch (TelegramApiException e) {
            e.printStackTrace();
        }
    }

    private void showUsersList(long chatId, int messageId) {
        EditMessageText em = new EditMessageText();
        em.setChatId(String.valueOf(chatId));
        em.setMessageId(messageId);
        em.setParseMode("Markdown");

        StringBuilder sb = new StringBuilder();
        sb.append("👥 *قائمة جميع المشتركين المسجلين بالبوت:*\n\n");

        try (Connection conn = DriverManager.getConnection(DB_URL);
             Statement stmt = conn.createStatement();
             ResultSet rs = stmt.executeQuery("SELECT * FROM users")) {
            while (rs.next()) {
                sb.append("👤 الاسم: *").append(rs.getString("username")).append("*\n")
                        .append("🆔 الآيدي: `").append(rs.getLong("chat_id")).append("`\n")
                        .append("💵 الرصيد: ").append(rs.getDouble("balance_usd")).append(" $ (").append(rs.getDouble("balance_jod")).append(" JOD)\n")
                        .append("📉 الخصم: %").append(rs.getDouble("discount")).append("\n")
                        .append("----------------------------\n");
            }
        } catch (SQLException e) {
            e.printStackTrace();
        }

        em.setText(sb.toString());

        InlineKeyboardMarkup markup = new InlineKeyboardMarkup();
        List<List<InlineKeyboardButton>> rows = new ArrayList<>();
        List<InlineKeyboardButton> row = new ArrayList<>();
        InlineKeyboardButton btnBack = new InlineKeyboardButton("🔙 رجوع للوحة الآدمن");
        btnBack.setCallbackData("ADMIN_PANEL");
        row.add(btnBack);
        rows.add(row);
        markup.setKeyboard(rows);
        em.setReplyMarkup(markup);

        try {
            execute(em);
        } catch (TelegramApiException e) {
            e.printStackTrace();
        }
    }

    private void showBroadcastMenu(long chatId, int messageId) {
        EditMessageText em = new EditMessageText();
        em.setChatId(String.valueOf(chatId));
        em.setMessageId(messageId);
        em.setText("📢 *تحديد الجمهور المستهدف بالإعلان:*");
        em.setParseMode("Markdown");

        InlineKeyboardMarkup markup = new InlineKeyboardMarkup();
        List<List<InlineKeyboardButton>> rows = new ArrayList<>();

        List<InlineKeyboardButton> r1 = new ArrayList<>();
        InlineKeyboardButton b1 = new InlineKeyboardButton("🌍 إعلان لجميع الأعضاء");
        b1.setCallbackData("BROADCAST_ALL");
        InlineKeyboardButton b2 = new InlineKeyboardButton("👤 إرسال لشخص محدد");
        b2.setCallbackData("BROADCAST_SPECIFIC");
        r1.add(b1);
        r1.add(b2);

        List<InlineKeyboardButton> r2 = new ArrayList<>();
        InlineKeyboardButton btnBack = new InlineKeyboardButton("🔙 رجوع");
        btnBack.setCallbackData("ADMIN_PANEL");
        r2.add(btnBack);

        rows.add(r1);
        rows.add(r2);
        markup.setKeyboard(rows);
        em.setReplyMarkup(markup);

        try {
            execute(em);
        } catch (TelegramApiException e) {
            e.printStackTrace();
        }
    }

    // --- العمليات على قواعد البيانات والمنطق البرمجي الداخلي ---

    private void registerUser(long chatId, String name) {
        try (Connection conn = DriverManager.getConnection(DB_URL);
             PreparedStatement ps = conn.prepareStatement(
                     "INSERT OR IGNORE INTO users (chat_id, username) VALUES (?, ?)")) {
            ps.setLong(1, chatId);
            ps.setString(2, name);
            ps.executeUpdate();
        } catch (SQLException e) {
            e.printStackTrace();
        }
    }

    private void addCategory(String name, int parentId) {
        try (Connection conn = DriverManager.getConnection(DB_URL);
             PreparedStatement ps = conn.prepareStatement("INSERT INTO categories (name, parent_id) VALUES (?, ?)")) {
            ps.setString(1, name);
            ps.setInt(2, parentId);
            ps.executeUpdate();
        } catch (SQLException e) {
            e.printStackTrace();
        }
    }

    private void deleteCategory(int catId) {
        try (Connection conn = DriverManager.getConnection(DB_URL)) {
            // حذف المنتجات التابعة
            try (PreparedStatement ps = conn.prepareStatement("DELETE FROM products WHERE category_id = ?")) {
                ps.setInt(1, catId);
                ps.executeUpdate();
            }
            // حذف القسم نفسه
            try (PreparedStatement ps = conn.prepareStatement("DELETE FROM categories WHERE id = ?")) {
                ps.setInt(1, catId);
                ps.executeUpdate();
            }
        } catch (SQLException e) {
            e.printStackTrace();
        }
    }

    private int getParentCategoryId(int childId) {
        try (Connection conn = DriverManager.getConnection(DB_URL);
             PreparedStatement ps = conn.prepareStatement("SELECT parent_id FROM categories WHERE id = ?")) {
            ps.setInt(1, childId);
            ResultSet rs = ps.executeQuery();
            if (rs.next()) {
                return rs.getInt("parent_id");
            }
        } catch (SQLException e) {
            e.printStackTrace();
        }
        return 0;
    }

    private void addProduct(int catId, String name, String desc, double priceJod, double priceUsd) {
        try (Connection conn = DriverManager.getConnection(DB_URL);
             PreparedStatement ps = conn.prepareStatement(
                     "INSERT INTO products (category_id, name, description, price_jod, price_usd) VALUES (?, ?, ?, ?, ?)")) {
            ps.setInt(1, catId);
            ps.setString(2, name);
            ps.setString(3, desc);
            ps.setDouble(4, priceJod);
            ps.setDouble(5, priceUsd);
            ps.executeUpdate();
        } catch (SQLException e) {
            e.printStackTrace();
        }
    }

    private void deleteProduct(int prodId) {
        try (Connection conn = DriverManager.getConnection(DB_URL);
             PreparedStatement ps = conn.prepareStatement("DELETE FROM products WHERE id = ?")) {
            ps.setInt(1, prodId);
            ps.executeUpdate();
        } catch (SQLException e) {
            e.printStackTrace();
        }
    }

    private String getProductName(int prodId) {
        try (Connection conn = DriverManager.getConnection(DB_URL);
             PreparedStatement ps = conn.prepareStatement("SELECT name FROM products WHERE id = ?")) {
            ps.setInt(1, prodId);
            ResultSet rs = ps.executeQuery();
            if (rs.next()) return rs.getString("name");
        } catch (SQLException e) {
            e.printStackTrace();
        }
        return "منتج غير معروف";
    }

    private double getUserDiscount(long userId) {
        try (Connection conn = DriverManager.getConnection(DB_URL);
             PreparedStatement ps = conn.prepareStatement("SELECT discount FROM users WHERE chat_id = ?")) {
            ps.setLong(1, userId);
            ResultSet rs = ps.executeQuery();
            if (rs.next()) return rs.getDouble("discount");
        } catch (SQLException e) {
            e.printStackTrace();
        }
        return 0.0;
    }

    private void updateUserDiscount(long userId, double discount) {
        try (Connection conn = DriverManager.getConnection(DB_URL);
             PreparedStatement ps = conn.prepareStatement("UPDATE users SET discount = ? WHERE chat_id = ?")) {
            ps.setDouble(1, discount);
            ps.setLong(2, userId);
            ps.executeUpdate();
        } catch (SQLException e) {
            e.printStackTrace();
        }
    }

    private int createOrder(long userId, int prodId, String info) {
        try (Connection conn = DriverManager.getConnection(DB_URL);
             PreparedStatement ps = conn.prepareStatement(
                     "INSERT INTO orders (user_id, product_id, info) VALUES (?, ?, ?)", Statement.RETURN_GENERATED_KEYS)) {
            ps.setLong(1, userId);
            ps.setInt(2, prodId);
            ps.setString(3, info);
            ps.executeUpdate();
            ResultSet rs = ps.getGeneratedKeys();
            if (rs.next()) return rs.getInt(1);
        } catch (SQLException e) {
            e.printStackTrace();
        }
        return 0;
    }

    private int createRechargeRequest(long userId, String txText) {
        // نستخدم نفس جدول الطلبات لتبسيط الحفظ ونحدد منتج افتراضي id = 0 ليعبر عن الشحن
        try (Connection conn = DriverManager.getConnection(DB_URL);
             PreparedStatement ps = conn.prepareStatement(
                     "INSERT INTO orders (user_id, product_id, info, status) VALUES (?, 0, ?, 'PENDING')", Statement.RETURN_GENERATED_KEYS)) {
            ps.setLong(1, userId);
            ps.setString(2, txText);
            ps.executeUpdate();
            ResultSet rs = ps.getGeneratedKeys();
            if (rs.next()) return rs.getInt(1);
        } catch (SQLException e) {
            e.printStackTrace();
        }
        return 0;
    }

    private void updateOrderStatus(int orderId, String status) {
        try (Connection conn = DriverManager.getConnection(DB_URL);
             PreparedStatement ps = conn.prepareStatement("UPDATE orders SET status = ? WHERE id = ?")) {
            ps.setString(1, status);
            ps.setInt(2, orderId);
            ps.executeUpdate();
        } catch (SQLException e) {
            e.printStackTrace();
        }
    }

    private void updateUserBalance(long userId, double diffJod, double diffUsd) {
        try (Connection conn = DriverManager.getConnection(DB_URL);
             PreparedStatement ps = conn.prepareStatement(
                     "UPDATE users SET balance_jod = balance_jod + ?, balance_usd = balance_usd + ? WHERE chat_id = ?")) {
            ps.setDouble(1, diffJod);
            ps.setDouble(2, diffUsd);
            ps.executeUpdate();
        } catch (SQLException e) {
            e.printStackTrace();
        }
    }

    private void processProductPurchaseAccept(int orderId, long userId, int prodId) {
        try (Connection conn = DriverManager.getConnection(DB_URL)) {
            // جلب أسعار المنتج
            double originalJod = 0, originalUsd = 0;
            try (PreparedStatement ps = conn.prepareStatement("SELECT price_jod, price_usd FROM products WHERE id = ?")) {
                ps.setInt(1, prodId);
                ResultSet rs = ps.executeQuery();
                if (rs.next()) {
                    originalJod = rs.getDouble("price_jod");
                    originalUsd = rs.getDouble("price_usd");
                }
            }

            // جلب بيانات العميل للتأكد من رصيده بعد الخصم المعتمد له
            double discount = getUserDiscount(userId);
            double finalJod = originalJod * (1 - (discount / 100));
            double finalUsd = originalUsd * (1 - (discount / 100));

            double userJod = 0, userUsd = 0;
            try (PreparedStatement ps = conn.prepareStatement("SELECT balance_jod, balance_usd FROM users WHERE chat_id = ?")) {
                ps.setLong(1, userId);
                ResultSet rs = ps.executeQuery();
                if (rs.next()) {
                    userJod = rs.getDouble("balance_jod");
                    userUsd = rs.getDouble("balance_usd");
                }
            }

            if (userUsd >= finalUsd) {
                // خصم الرصيد وتحديث حالة الطلب
                updateUserBalance(userId, -finalJod, -finalUsd);
                updateOrderStatus(orderId, "ACCEPTED");
                sendMessage(userId, "🎉 تم قبول طلبك بنجاح! تم خصم بقيمة `" + finalUsd + " $` / `" + finalJod + " د.أ` من رصيدك الحالي.");
                sendMessage(ADMIN_ID, "✅ تم إتمام وتأكيد الشراء للزبون، وتم الخصم من حسابه بنجاح.");
            } else {
                sendMessage(userId, "⚠️ رصيدك الحالي غير كافي لإتمام هذه الخدمة، يرجى تعبئة وشحن حسابك أولاً.");
                sendMessage(ADMIN_ID, "🛑 محاولة قبول فاشلة: رصيد الزبون لا يكفي لإتمام عملية الشراء!");
            }

        } catch (SQLException e) {
            e.printStackTrace();
        }
    }

    private void broadcastToAll(String text) {
        try (Connection conn = DriverManager.getConnection(DB_URL);
             Statement stmt = conn.createStatement();
             ResultSet rs = stmt.executeQuery("SELECT chat_id FROM users")) {
            while (rs.next()) {
                sendMessage(rs.getLong("chat_id"), "📢 إعلان هام:\n\n" + text);
            }
        } catch (SQLException e) {
            e.printStackTrace();
        }
    }

    // --- إرسال الرسائل وتعديلها ---
    private void sendMessage(long chatId, String text) {
        SendMessage sm = new SendMessage();
        sm.setChatId(String.valueOf(chatId));
        sm.setText(text);
        sm.setParseMode("Markdown");
        try {
            execute(sm);
        } catch (TelegramApiException e) {
            e.printStackTrace();
        }
    }

    private void sendAdminMessageWithMarkup(String text, InlineKeyboardMarkup markup) {
        SendMessage sm = new SendMessage();
        sm.setChatId(String.valueOf(ADMIN_ID));
        sm.setText(text);
        sm.setParseMode("Markdown");
        sm.setReplyMarkup(markup);
        try {
            execute(sm);
        } catch (TelegramApiException e) {
            e.printStackTrace();
        }
    }

    private void editMessage(long chatId, int messageId, String text) {
        EditMessageText em = new EditMessageText();
        em.setChatId(String.valueOf(chatId));
        em.setMessageId(messageId);
        em.setText(text);
        em.setParseMode("Markdown");
        try {
            execute(em);
        } catch (TelegramApiException e) {
            e.printStackTrace();
        }
    }
}
